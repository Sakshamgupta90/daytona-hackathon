import os
import json
import logging
from typing import Dict, Any, Generator, Optional

from person1_compiler.pipeline import compile_to_mcp, apply_feedback_and_recompile
from person1_compiler.benchmark import MCPBenchmarkEvaluator
from deployment_stage.deployer_agent.schemas import MCPBundle
from deployment_stage.deployer_agent.deployer import DeployerAgent
from deployment_stage.tester_agent.tester import TesterAgent

logger = logging.getLogger("MCPForgeOrchestrator")

class MCPForgeOrchestrator:
    """
    Master Orchestrator connecting all 3 Persons:
    Person 1 (Compiler) -> Person 2 (Daytona Deployer & Tester) -> Self-Healing Loop -> Verification.
    """

    @classmethod
    def run(
        cls,
        raw_payload: Dict[str, Any],
        max_healing_retries: int = 2,
        use_mock_sandbox: bool = False
    ) -> Generator[Dict[str, Any], None, Dict[str, Any]]:
        """
        Executes the end-to-end multi-agent pipeline and yields progress status updates for the UI.
        """
        # -------------------------------------------------------------
        # STEP 1: Person 1 Ingestion & FastMCP Compilation
        # -------------------------------------------------------------
        yield {
            "step": "COMPILING",
            "message": "🧠 Agent 1 (Planner) & 💻 Agent 2 (Coder): Formulating tool schemas and FastMCP server...",
            "progress": 20
        }

        try:
            bundle_dict = compile_to_mcp(raw_payload)
        except Exception as e:
            yield {
                "step": "ERROR",
                "message": f"Compilation failed: {str(e)}",
                "progress": 100,
                "error": str(e)
            }
            return

        service_name = bundle_dict.get("metadata", {}).get("service_name", "MCPService")
        auth_data = raw_payload.get("auth", {}) or {}
        env_var_name = auth_data.get("env_var_name", "API_KEY")
        test_token = auth_data.get("test_token") or "dummy-token"
        base_url = raw_payload.get("base_url") or bundle_dict.get("metadata", {}).get("base_url", "")

        # -------------------------------------------------------------
        # STEP 2: Adapt to Person 2 MCPBundle Contract
        # -------------------------------------------------------------
        bundle_obj = MCPBundle(
            **{
                "server.py": bundle_dict["server.py"],
                "requirements.txt": bundle_dict["requirements.txt"],
                "test_protocol.json": bundle_dict["test_protocol.json"],
                "run_tests.py": bundle_dict["run_tests.py"],
                "env_vars": {
                    env_var_name: test_token,
                    "API_BASE_URL": base_url
                }
            }
        )

        # -------------------------------------------------------------
        # STEP 3: Person 2 Daytona Provisioning & Deployment
        # -------------------------------------------------------------
        yield {
            "step": "DEPLOYING",
            "message": f"🚀 Agent 3 (Deployer): Provisioning Daytona Sandbox & mounting {service_name}...",
            "progress": 50,
            "bundle": bundle_dict
        }

        deployer = DeployerAgent()
        deploy_output = deployer.deploy(bundle_obj.to_coder_output())

        if deploy_output.status != "DEPLOYED":
            yield {
                "step": "DEPLOYMENT_FAILED",
                "message": f"❌ Daytona Deployment Failed: {deploy_output.error_message}",
                "progress": 100,
                "deploy_output": deploy_output.model_dump()
            }
            return

        # -------------------------------------------------------------
        # STEP 4: Person 2 Functional Testing inside Daytona
        # -------------------------------------------------------------
        yield {
            "step": "TESTING",
            "message": f"🧪 Agent 4 (Tester): Executing test suite in Daytona Sandbox ({deploy_output.workspace_id})...",
            "progress": 75,
            "workspace_id": deploy_output.workspace_id
        }

        tester = TesterAgent()
        tester_output = tester.test(deploy_output)

        # -------------------------------------------------------------
        # STEP 5: Self-Healing Loop (if tests fail)
        # -------------------------------------------------------------
        retry_count = 0
        while tester_output.status == "TESTS_FAILED" and retry_count < max_healing_retries:
            retry_count += 1
            feedback = tester_output.feedback_report
            feedback_dict = feedback.model_dump() if feedback else {
                "status": "FAIL",
                "error_message": tester_output.error_message or "Test suite failed",
                "failing_tool": "unknown"
            }

            yield {
                "step": "SELF_HEALING",
                "message": f"🔄 Autonomous Self-Healing (Attempt {retry_count}/{max_healing_retries}): Auto-patching server.py based on Daytona test failure...",
                "progress": 70 + (retry_count * 5),
                "feedback": feedback_dict
            }

            try:
                # Patch and re-compile
                bundle_dict = apply_feedback_and_recompile(feedback_dict)
                
                # Re-deploy to Daytona
                bundle_obj = MCPBundle(
                    **{
                        "server.py": bundle_dict["server.py"],
                        "requirements.txt": bundle_dict["requirements.txt"],
                        "test_protocol.json": bundle_dict["test_protocol.json"],
                        "run_tests.py": bundle_dict["run_tests.py"],
                        "env_vars": {
                            env_var_name: test_token,
                            "API_BASE_URL": base_url
                        }
                    }
                )
                deploy_output = deployer.deploy(bundle_obj.to_coder_output())
                if deploy_output.status == "DEPLOYED":
                    tester_output = tester.test(deploy_output)
            except Exception as patch_err:
                logger.error(f"Self-healing iteration failed: {patch_err}")
                break

        # -------------------------------------------------------------
        # STEP 6: Benchmark & Final Package
        # -------------------------------------------------------------
        yield {
            "step": "EVALUATING",
            "message": "📊 Evaluating Schema Completeness & Security Hardening Scorecard...",
            "progress": 95
        }

        benchmark_report = MCPBenchmarkEvaluator.evaluate_mcp_bundle(bundle_dict)

        final_result = {
            "status": "SUCCESS" if tester_output.status == "TESTS_PASSED" else "PARTIAL_PASS",
            "step": "COMPLETED",
            "message": "✅ FastMCP Server Compiled, Deployed, Tested & Verified in Daytona!",
            "progress": 100,
            "bundle": bundle_dict,
            "deploy_output": deploy_output.model_dump(),
            "tester_output": tester_output.model_dump(),
            "benchmark_report": benchmark_report,
            "workspace_id": deploy_output.workspace_id,
            "self_healed": retry_count > 0,
            "healing_attempts": retry_count
        }

        yield final_result
        return final_result

if __name__ == "__main__":
    import sys
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding='utf-8')

    sample_file = os.path.join(os.path.dirname(__file__), "person1_compiler", "sample_inputs", "raw_github_input.json")
    with open(sample_file, "r", encoding="utf-8") as f:
        payload = json.load(f)

    print("\n--- Testing MCPForgeOrchestrator End-to-End ---")
    for event in MCPForgeOrchestrator.run(payload):
        step = event.get('step')
        msg = event.get('message')
        print(f"[{step}] {msg}")
        if step == "COMPLETED":
            print(f"-> Status: {event.get('status')}")
            print(f"-> Workspace ID: {event.get('workspace_id')}")
            print(f"-> Benchmark Score: {event.get('benchmark_report', {}).get('overall_score')}")
