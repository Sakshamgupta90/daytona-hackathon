import keyword
import os
import json
import logging
import re
from typing import Dict, Any, List, Optional, Set
from dotenv import load_dotenv

try:
    from shared.models import (
        NormalizedServiceSpec,
        PlannedMCPBlueprint,
        PlannedTool,
        PlannedToolParameter,
        PlannedTestCase,
        FeedbackReport,
        ParameterLocation,
    )
except ImportError:
    from models import (
        NormalizedServiceSpec,
        PlannedMCPBlueprint,
        PlannedTool,
        PlannedToolParameter,
        PlannedTestCase,
        FeedbackReport,
        ParameterLocation,
    )

load_dotenv()
logger = logging.getLogger("MCPForge.Planner")


class PlannerAgent:
    """
    Transforms NormalizedServiceSpec into PlannedMCPBlueprint with agentic tool descriptions,
    type-safe parameter bindings, and synthetic test suites.
    """

    PYTHON_KEYWORDS: Set[str] = set(keyword.kwlist) | {
        "self", "cls", "schema", "type", "format", "id", "filter", "input", "output"
    }

    def __init__(self, use_llm: bool = True):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.use_llm = use_llm and bool(self.api_key and not self.api_key.startswith("your-") and not self.api_key.startswith("sk-placeholder"))

    def plan(self, spec: NormalizedServiceSpec) -> PlannedMCPBlueprint:
        if self.use_llm:
            try:
                return self._plan_with_llm(spec)
            except Exception as e:
                logger.warning("[PlannerAgent] LLM Planning failed (%s), falling back to deterministic planning.", e)
                return self._plan_deterministic(spec)
        return self._plan_deterministic(spec)

    @classmethod
    def sanitize_identifier(cls, name: str) -> str:
        """Sanitizes raw API parameter names into valid, non-reserved Python variable identifiers."""
        clean = re.sub(r'[^a-zA-Z0-9_]', '_', name).strip('_')
        if not clean or clean[0].isdigit():
            clean = f"param_{clean}"
        clean = clean.lower()
        if clean in cls.PYTHON_KEYWORDS:
            clean = f"{clean}_"
        return clean

    def _plan_deterministic(self, spec: NormalizedServiceSpec) -> PlannedMCPBlueprint:
        planned_tools: List[PlannedTool] = []

        for ep in spec.endpoints:
            op_name = ep.operation_id or f"{ep.method.lower()}_{re.sub(r'[^a-zA-Z0-9]+', '_', ep.path.strip('/')).strip('_')}"
            clean_name = re.sub(r'[^a-zA-Z0-9_]+', '_', op_name).lower().strip('_') or f"{ep.method.lower()}_tool"
            if clean_name[0].isdigit():
                clean_name = f"tool_{clean_name}"

            doc = ep.description or ep.summary or f"Executes {ep.method} on {ep.path}"
            agent_docstring = (
                f"{doc.strip()} Use when the user requests {spec.service_name} {ep.method} operations on '{ep.path}'."
            )

            planned_params: List[PlannedToolParameter] = []
            sample_args: Dict[str, Any] = {}
            boundary_args: Dict[str, Any] = {}

            for p in ep.parameters:
                py_name = self.sanitize_identifier(p.name)
                py_type = self._map_to_python_type(p.type, p.required)
                default_val = str(p.default) if p.default is not None else ("None" if not p.required else None)

                planned_params.append(
                    PlannedToolParameter(
                        name=py_name,
                        raw_name=p.name,
                        python_type=py_type,
                        description=p.description or f"Parameter {p.name}",
                        required=p.required,
                        location=p.location,
                        default_value=default_val,
                    )
                )

                sample_val = self._generate_sample_value(p.name, p.type, p.enum_values)
                if p.required:
                    sample_args[py_name] = sample_val
                boundary_args[py_name] = sample_val

            test_cases = [
                PlannedTestCase(
                    test_id=f"test_{clean_name}_happy_path",
                    description=f"Standard valid execution for {clean_name}",
                    input_arguments=sample_args,
                    expected_http_status=200,
                )
            ]

            if len(boundary_args) > len(sample_args):
                test_cases.append(
                    PlannedTestCase(
                        test_id=f"test_{clean_name}_comprehensive",
                        description=f"Full parameter validation test for {clean_name}",
                        input_arguments=boundary_args,
                        expected_http_status=200,
                    )
                )

            planned_tools.append(
                PlannedTool(
                    tool_name=clean_name,
                    docstring=agent_docstring,
                    http_method=ep.method,
                    endpoint_path=ep.path,
                    parameters=planned_params,
                    test_cases=test_cases,
                )
            )

        return PlannedMCPBlueprint(
            service_name=spec.service_name,
            base_url=spec.base_url,
            auth=spec.auth,
            tools=planned_tools,
            system_instruction=f"Production FastMCP Server providing curated developer tools for {spec.service_name}.",
        )

    def _plan_with_llm(self, spec: NormalizedServiceSpec) -> PlannedMCPBlueprint:
        from openai import OpenAI
        client = OpenAI(api_key=self.api_key, timeout=30.0)

        prompt = f"""You are a Principal AI Tool Architect.
Analyze this API specification for '{spec.service_name}' and produce a production-grade PlannedMCPBlueprint:
1. Tool names MUST be snake_case verbs (e.g. 'get_repository', 'create_issue', 'list_issue_comments').
2. Parameter names MUST be valid Python variable identifiers (e.g. no dashes, not Python keywords).
3. Parameter 'raw_name' must retain the exact API wire parameter name.
4. Docstrings must explicitly explain to the LLM agent WHEN and WHY to call the tool.
5. Generate at least 1 valid happy_path test case per tool with realistic arguments.

Input Spec:
{spec.model_dump_json(indent=2)}
"""
        response = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a specialized compiler agent. Output strictly valid PlannedMCPBlueprint JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format=PlannedMCPBlueprint,
        )
        return response.choices[0].message.parsed

    def apply_feedback(self, blueprint: PlannedMCPBlueprint, feedback: FeedbackReport) -> PlannedMCPBlueprint:
        """
        Diagnoses failures reported from Daytona test runner or security fuzzing,
        patches the blueprint schema, docstrings, and test arguments.
        """
        target_tool = feedback.failing_tool
        for tool in blueprint.tools:
            if not target_tool or tool.tool_name == target_tool or (target_tool and target_tool in tool.tool_name):
                # Apply suggested fix to docstring & guardrails
                if feedback.suggested_fix:
                    if "[Guardrail:" not in tool.docstring:
                        tool.docstring += f" [Guardrail: {feedback.suggested_fix}]"

                # Handle type errors
                if feedback.error_category == "type_validation_error":
                    for param in tool.parameters:
                        if feedback.tested_payload and param.name in feedback.tested_payload:
                            val = feedback.tested_payload[param.name]
                            if isinstance(val, int) and "str" in param.python_type:
                                param.python_type = "Union[str, int]"
                            elif isinstance(val, str) and "int" in param.python_type:
                                param.python_type = "Union[int, str]"

                # Update test cases with verified payload
                if feedback.tested_payload and tool.test_cases:
                    tool.test_cases[0].input_arguments.update(feedback.tested_payload)

        return blueprint

    @staticmethod
    def _map_to_python_type(schema_type: str, required: bool) -> str:
        base_type = "str"
        st = schema_type.lower()
        if st in ["integer", "int"]:
            base_type = "int"
        elif st in ["number", "float", "double"]:
            base_type = "float"
        elif st in ["boolean", "bool"]:
            base_type = "bool"
        elif st in ["array", "list"]:
            base_type = "List[Any]"
        elif st in ["object", "dict"]:
            base_type = "Dict[str, Any]"

        if not required:
            return f"Optional[{base_type}]"
        return base_type

    @staticmethod
    def _generate_sample_value(param_name: str, param_type: str, enum_values: Optional[List[str]] = None) -> Any:
        if enum_values and len(enum_values) > 0:
            return enum_values[0]

        p_lower = param_name.lower()
        if "owner" in p_lower or "org" in p_lower:
            return "octocat"
        if "repo" in p_lower:
            return "Hello-World"
        if "username" in p_lower or "user" in p_lower:
            return "octocat"
        if "issue_number" in p_lower or "number" in p_lower or "id" in p_lower:
            return 1
        if "title" in p_lower:
            return "Bug: Automated Test Diagnostic Run"
        if "body" in p_lower or "content" in p_lower:
            return "Detailed issue description for testing purposes."
        if "state" in p_lower:
            return "open"
        if "per_page" in p_lower or "limit" in p_lower:
            return 30
        if "page" in p_lower:
            return 1

        if param_type in ["integer", "int"]:
            return 1
        if param_type in ["number", "float", "double"]:
            return 1.0
        if param_type in ["boolean", "bool"]:
            return True
        if param_type in ["array", "list"]:
            return ["sample_item"]
        if param_type in ["object", "dict"]:
            return {"key": "value"}

        return "sample_value"

