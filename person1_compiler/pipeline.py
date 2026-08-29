import os
import json
import logging
import threading
from typing import Dict, Any, Union, Optional

try:
    from shared.models import RawUIPayload, FeedbackReport, PlannedMCPBlueprint
except ImportError:
    from models import RawUIPayload, FeedbackReport, PlannedMCPBlueprint

from .ingest import SpecNormalizer
from .planner import PlannerAgent
from .coder import CoderAgent

logger = logging.getLogger("MCPForge.Pipeline")

_REGISTRY_LOCK = threading.Lock()
_BLUEPRINT_REGISTRY: Dict[str, PlannedMCPBlueprint] = {}
_LAST_SERVICE_NAME: Optional[str] = None


def compile_to_mcp(raw_payload: Union[Dict[str, Any], str, RawUIPayload], use_llm: bool = True) -> Dict[str, Any]:
    """
    Main Compiler Entrypoint:
    Transforms Raw UI Payload -> Normalized Spec -> Planned Blueprint -> Production Code Bundle.
    """
    global _LAST_SERVICE_NAME

    if isinstance(raw_payload, str):
        content_str = raw_payload.strip()
        if content_str.startswith("curl ") or content_str.startswith("curl\n"):
            ui_model = RawUIPayload(spec_format="curl", spec_content=content_str)
        else:
            try:
                parsed_json = json.loads(content_str)
                if isinstance(parsed_json, dict) and ("paths" in parsed_json or "swagger" in parsed_json or "openapi" in parsed_json):
                    ui_model = RawUIPayload(spec_format="openapi_json", spec_content=parsed_json)
                elif isinstance(parsed_json, dict) and "spec_content" in parsed_json:
                    ui_model = RawUIPayload(**parsed_json)
                else:
                    ui_model = RawUIPayload(spec_format="openapi_json", spec_content=parsed_json)
            except Exception:
                ui_model = RawUIPayload(spec_format="openapi_yaml", spec_content=content_str)
    elif isinstance(raw_payload, dict):
        if "spec_content" in raw_payload:
            ui_model = RawUIPayload(**raw_payload)
        else:
            ui_model = RawUIPayload(spec_format="openapi_json", spec_content=raw_payload)
    elif isinstance(raw_payload, RawUIPayload):
        ui_model = raw_payload
    else:
        raise ValueError(f"Invalid raw_payload type: {type(raw_payload)}. Expected dict, str, or RawUIPayload.")

    spec = SpecNormalizer.normalize(ui_model)
    planner = PlannerAgent(use_llm=use_llm)
    blueprint = planner.plan(spec)

    with _REGISTRY_LOCK:
        _BLUEPRINT_REGISTRY[blueprint.service_name] = blueprint
        _LAST_SERVICE_NAME = blueprint.service_name

    bundle = CoderAgent.generate_bundle(blueprint)
    bundle["service_spec"] = spec.model_dump()
    bundle["blueprint"] = blueprint.model_dump()

    return bundle


def apply_feedback_and_recompile(
    feedback_data: Union[Dict[str, Any], FeedbackReport],
    service_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Self-Healing Loop Entrypoint:
    Applies failure feedback from Daytona test runner or security fuzzing, patches the blueprint,
    and re-emits a hardened code bundle.
    """
    global _LAST_SERVICE_NAME

    if isinstance(feedback_data, dict):
        feedback = FeedbackReport(**feedback_data)
    elif isinstance(feedback_data, FeedbackReport):
        feedback = feedback_data
    else:
        raise ValueError(f"Invalid feedback_data type: {type(feedback_data)}. Expected dict or FeedbackReport.")

    target_svc = service_name or feedback.service_name or _LAST_SERVICE_NAME

    with _REGISTRY_LOCK:
        blueprint = _BLUEPRINT_REGISTRY.get(target_svc) if target_svc else None
        if not blueprint and _BLUEPRINT_REGISTRY:
            target_svc = next(iter(_BLUEPRINT_REGISTRY.keys()))
            blueprint = _BLUEPRINT_REGISTRY.get(target_svc)

    if not blueprint:
        raise RuntimeError(
            f"No active blueprint found for service '{target_svc}'. "
            "Please compile an API spec with compile_to_mcp() first."
        )

    planner = PlannerAgent(use_llm=False)
    patched_blueprint = planner.apply_feedback(blueprint, feedback)

    with _REGISTRY_LOCK:
        _BLUEPRINT_REGISTRY[patched_blueprint.service_name] = patched_blueprint

    repaired_bundle = CoderAgent.generate_bundle(patched_blueprint)
    repaired_bundle["is_patched"] = True
    repaired_bundle["patch_reason"] = feedback.error_message
    repaired_bundle["service_spec"] = repaired_bundle.get("service_spec")
    repaired_bundle["blueprint"] = patched_blueprint.model_dump()

    return repaired_bundle


if __name__ == "__main__":
    sample_file = os.path.join(os.path.dirname(__file__), "sample_inputs", "raw_github_input.json")
    with open(sample_file, "r", encoding="utf-8") as f:
        github_payload = json.load(f)

    print("[Pipeline] Compiling GitHub Issues showcase API to FastMCP bundle...")
    result = compile_to_mcp(github_payload)
    print(f"-> Successfully generated server.py for '{result['metadata']['service_name']}'!")
    print(f"-> Tools created: {result['metadata']['tools']}")
    print(f"-> Test Protocol generated with {len(result['test_protocol.json']['tests'])} test cases.")

