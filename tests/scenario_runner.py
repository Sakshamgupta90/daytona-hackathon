"""Shared runner for one MCP Forge deployment-and-test scenario."""
import logging
import os
import sys

from dotenv import load_dotenv

from deployment_stage.deployer_agent.deployer import DeployerAgent
from deployment_stage.tester_agent.tester import TesterAgent


def run_scenario(*, name: str, coder_output, expected_status: str) -> None:
    """Run exactly one Coder → Deployer → Tester scenario and show its route."""
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(message)s",
        stream=sys.stdout,
    )

    is_mock = os.getenv("MOCK_SANDBOX", "true").lower() in ("true", "1", "yes")
    mode = "LOCAL MOCK" if is_mock else "DAYTONA CLOUD LIVE"

    print("\n" + "=" * 68)
    print(f"  MCP FORGE — SINGLE SCENARIO: {name}")
    print("=" * 68)
    print(f"  Sandbox mode : {mode}")
    print(f"  Project      : {coder_output.project_name}")
    print(f"  Expected     : {expected_status}")

    print("\n▶ Agent 3 — Deployer: provisioning and setting up sandbox")
    deployment = DeployerAgent().deploy(coder_output)
    if deployment.status != "DEPLOYED":
        print("\n❌ ROUTE: deployment failed before Tester Agent could run")
        print(f"   Reason: {deployment.error_message}")
        raise SystemExit(1)

    print("\n▶ Agent 4 — Tester: executing test commands")
    reports_dir = os.path.join("tests", "reports", name)
    outcome = TesterAgent(report_output_dir=reports_dir).run(deployment)

    print("\n" + "─" * 68)
    print("  ROUTING RESULT")
    print("─" * 68)
    if outcome.status == "TESTS_PASSED":
        print("  Tester → Agent 5 (Security)")
        print("  Reason: all test commands succeeded.")
        print("  Payload: verified deployment metadata prepared for Security.")
    else:
        print("  Tester → Agent 1 (Planner)")
        print("  Reason: one or more test commands failed.")
        if outcome.diagnostic_report:
            print(f"  Diagnostic: {outcome.diagnostic_report.root_cause_summary}")
            print(f"  Report folder: {reports_dir}/")
        elif outcome.error_message:
            print(f"  Error: {outcome.error_message}")

    matched = outcome.status == expected_status
    print(f"\n  Expected status: {expected_status}")
    print(f"  Actual status  : {outcome.status}")
    print(f"  Scenario result: {'✅ PASS' if matched else '❌ MISMATCH'}")
    print("─" * 68 + "\n")
    raise SystemExit(0 if matched else 1)
