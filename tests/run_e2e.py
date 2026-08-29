"""
MCP Forge — End-to-End Pipeline Test Suite
==========================================
Tests Agent 3 (Deployer) → Agent 4 (Tester) with three scenarios:

  ✅  Case 1: math-mcp-server       — correct server, all tests pass
               → routes to Agent 5 (Security) [stub]

  ❌  Case 2: buggy-math-mcp-server — wrong return values, AssertionErrors
               → diagnostic JSON sent to Agent 1 (Planner) [stub]

  ❌  Case 3: missing-dep-mcp-server — numpy not in requirements, ImportError
               → diagnostic JSON sent to Agent 1 (Planner) [stub]

Run:
  MOCK_SANDBOX=true  python3 -m tests.run_e2e   # fast, local, no cost
  MOCK_SANDBOX=false python3 -m tests.run_e2e   # real Daytona Cloud
"""
import json
import logging
import os
import sys
import time
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

# ── Logging ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    stream=sys.stdout,
)

# ── Imports ──────────────────────────────────────────────────
from deployment_stage.deployer_agent.deployer import DeployerAgent
from deployment_stage.tester_agent.tester import TesterAgent
from tests.fixtures import (
    PASSING_MATH_SERVER,
    FAILING_MATH_SERVER,
    FAILING_IMPORT_SERVER,
)

REPORTS_DIR = "./tests/reports"
os.makedirs(REPORTS_DIR, exist_ok=True)


# ════════════════════════════════════════════════════════════
#  Helpers
# ════════════════════════════════════════════════════════════
def banner(text: str, char: str = "═", width: int = 62) -> None:
    print("\n" + char * width)
    print(f"  {text}")
    print(char * width)


def section(text: str) -> None:
    print(f"\n{'─' * 62}")
    print(f"  {text}")
    print(f"{'─' * 62}")


def run_case(label: str, case_num: int, coder_output, expected: str) -> dict:
    """
    Runs one Deployer → Tester pipeline case.
    Returns a summary dict for the final report.
    """
    banner(
        f"TEST CASE {case_num}: {label}  "
        f"(expected: {expected})",
        char="█",
    )
    print(f"  Project      : {coder_output.project_name}")
    print(f"  Language     : {coder_output.language} {coder_output.runtime_version}")
    print(f"  Files        : {[f.path for f in coder_output.files]}")
    print(f"  Test Cmds    : {coder_output.test_commands}")
    print(f"  Env Vars     : {coder_output.env_vars}")

    start = time.time()

    # ── Phase 1: Deploy ──────────────────────────────────────
    section("Phase 1 — Agent 3 (Deployer Agent): Provisioning Sandbox")
    deployer = DeployerAgent()
    deployer_output = deployer.deploy(coder_output)

    if deployer_output.status != "DEPLOYED":
        print(f"\n  ❌ Deployment failed: {deployer_output.error_message}")
        return {
            "case": case_num,
            "label": label,
            "expected": expected,
            "actual": "DEPLOY_FAILED",
            "passed": False,
            "duration_s": round(time.time() - start, 2),
        }

    print(f"\n  ✅ Deployed → Workspace ID: {deployer_output.workspace_id}")
    print(f"     Files uploaded: {deployer_output.deployed_files}")

    # ── Phase 2: Test ─────────────────────────────────────────
    section("Phase 2 — Agent 4 (Tester Agent): Running Tests in Sandbox")
    tester = TesterAgent(report_output_dir=REPORTS_DIR)
    tester_output = tester.run(deployer_output)

    duration = round(time.time() - start, 2)
    actual = tester_output.status

    # ── Case result ───────────────────────────────────────────
    matched = actual == expected
    result_icon = "✅ PASS" if matched else "❌ MISMATCH"

    banner(
        f"CASE {case_num} RESULT: {result_icon}  "
        f"({actual})  [{duration}s]",
        char="─",
        width=62,
    )

    if tester_output.diagnostic_report:
        dr = tester_output.diagnostic_report
        print(f"  📄 Diagnostic report ID : {dr.report_id}")
        print(f"  📁 Saved to             : {REPORTS_DIR}/")

    return {
        "case": case_num,
        "label": label,
        "expected": expected,
        "actual": actual,
        "passed": matched,
        "workspace_id": deployer_output.workspace_id,
        "duration_s": duration,
        "report_id": (
            tester_output.diagnostic_report.report_id
            if tester_output.diagnostic_report
            else None
        ),
    }


# ════════════════════════════════════════════════════════════
#  Main
# ════════════════════════════════════════════════════════════
def main():
    mode = os.getenv("MOCK_SANDBOX", "true")
    is_mock = mode.lower() in ("true", "1", "yes")

    banner(
        "MCP FORGE — END-TO-END PIPELINE TEST SUITE",
        char="═",
        width=62,
    )
    print(f"  Sandbox Mode : {'🔲 LOCAL MOCK (no cost)' if is_mock else '🌍 DAYTONA CLOUD LIVE'}")
    print(f"  Region       : {os.getenv('DAYTONA_TARGET', 'eu').upper()}")
    print(f"  Started at   : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Reports dir  : {REPORTS_DIR}/")

    results = []

    # ── Case 1: Passing calculator ────────────────────────────
    results.append(run_case(
        label="Correct Math MCP Server (all tests pass)",
        case_num=1,
        coder_output=PASSING_MATH_SERVER,
        expected="TESTS_PASSED",
    ))

    # ── Case 2: Buggy calculator (assertion failures) ─────────
    results.append(run_case(
        label="Buggy Math MCP Server (wrong return values)",
        case_num=2,
        coder_output=FAILING_MATH_SERVER,
        expected="TESTS_FAILED",
    ))

    # ── Case 3: Missing dependency (ImportError) ──────────────
    results.append(run_case(
        label="Missing Dependency Server (numpy not installed)",
        case_num=3,
        coder_output=FAILING_IMPORT_SERVER,
        expected="TESTS_FAILED",
    ))

    # ── Final Summary ─────────────────────────────────────────
    banner("FINAL TEST SUITE SUMMARY", char="═", width=62)
    total   = len(results)
    passed  = sum(1 for r in results if r["passed"])
    failed  = total - passed

    for r in results:
        icon = "✅" if r["passed"] else "❌"
        report_note = f" | report: {r['report_id'][:8]}" if r["report_id"] else ""
        print(
            f"  {icon} Case {r['case']}: {r['label'][:45]:<45} "
            f"({r['actual']}) [{r['duration_s']}s]{report_note}"
        )

    print(f"\n  Total: {total}  |  Passed: {passed}  |  Failed: {failed}")

    # ── Save suite summary JSON ───────────────────────────────
    summary_path = os.path.join(REPORTS_DIR, "suite_summary.json")
    with open(summary_path, "w") as f:
        json.dump(
            {
                "run_at": datetime.now().isoformat(),
                "sandbox_mode": "MOCK" if is_mock else "LIVE",
                "total": total,
                "passed": passed,
                "failed": failed,
                "cases": results,
            },
            f,
            indent=2,
        )
    print(f"\n  📊 Suite summary saved → {summary_path}")
    print()

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
