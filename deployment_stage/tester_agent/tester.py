"""
Tester Agent - Core Agent (Agent 4)
Orchestrates: execute tests → evaluate results → route to Agent 5 (Security)
or generate structured diagnostic report → route to Agent 1 (Planner).
Leaves the Daytona sandbox active after evaluation for follow-up agents.
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from .schemas import (
    DiagnosticReport,
    FeedbackReport,
    TestCommandResult,
    TestReport,
    TesterOutput,
    ToolResult,
)
from .executor import SandboxTestExecutor
from .log_parser import LogParser

logger = logging.getLogger("TesterAgent")


class TesterAgent:
    """
    Agent 4: Tester Agent

    Accepts a DeployerOutput (active sandbox workspace) and:
      1. Runs all test_commands inside the Daytona sandbox.
      2. Evaluates pass/fail for each command.
      3a. SUCCESS → prints "Sending to Agent 5 (Security)" + hands off payload.
      3b. FAIL    → builds structured DiagnosticReport JSON → prints "Sending to
                    Agent 1 (Planner)" + saves report to disk.
      4. Leaves the Daytona sandbox workspace active for inspection or handoff.
    """

    def __init__(self, report_output_dir: str = "./tester_reports"):
        """
        Args:
            report_output_dir: Directory where diagnostic JSON reports are saved on failure.
        """
        import os
        self.report_output_dir = report_output_dir
        os.makedirs(self.report_output_dir, exist_ok=True)

    # ─────────────────────────────────────────────
    #  Public entry point
    # ─────────────────────────────────────────────
    def run(self, deployer_output) -> TesterOutput:
        """
        Main entry point. Accepts a DeployerOutput object from Deployer Agent.

        Args:
            deployer_output: DeployerOutput from Agent 3 (Deployer Agent)

        Returns:
            TesterOutput with status TESTS_PASSED or TESTS_FAILED
        """
        workspace_id   = deployer_output.workspace_id
        project_name   = deployer_output.project_name
        sandbox_mgr    = deployer_output.raw_workspace_handle
        test_commands  = deployer_output.test_commands

        logger.info("=" * 60)
        logger.info(f"TesterAgent starting for project: {project_name}")
        logger.info(f"Workspace ID : {workspace_id}")
        logger.info(f"Test commands: {test_commands}")
        logger.info("=" * 60)

        try:
            # ── Step 1: Execute all test commands in sandbox ──
            executor = SandboxTestExecutor(
                sandbox_manager=sandbox_mgr,
                workspace_id=workspace_id,
            )
            results = executor.run_all(test_commands)

            # ── Step 2: Evaluate overall pass/fail ──
            total   = len(results)
            passed  = sum(1 for r in results if r.passed)
            failed  = total - passed
            all_ok  = (failed == 0 and total > 0)

            # ── Step 3: Route based on result ──
            if all_ok:
                output = self._handle_success(
                    workspace_id=workspace_id,
                    project_name=project_name,
                    results=results,
                    deployer_output=deployer_output,
                )
            else:
                output = self._handle_failure(
                    workspace_id=workspace_id,
                    project_name=project_name,
                    results=results,
                    total=total,
                    passed=passed,
                    failed=failed,
                    test_protocol=deployer_output.test_protocol,
                )

        except Exception as exc:
            logger.exception(f"Unexpected error in TesterAgent: {exc}")
            output = TesterOutput(
                workspace_id=workspace_id,
                project_name=project_name,
                status="TESTS_FAILED",
                error_message=f"TesterAgent internal error: {str(exc)}",
            )

        finally:
            # ── Step 4: Retain sandbox for the next agent / inspection ──
            logger.info(f"Keeping sandbox active after testing: {workspace_id}")
            print(f"\n🟢 Sandbox [{workspace_id}] retained after testing.\n")

        return output

    # ─────────────────────────────────────────────
    #  Success path → Agent 5 (Security)
    # ─────────────────────────────────────────────
    def _handle_success(
        self,
        workspace_id: str,
        project_name: str,
        results: list,
        deployer_output,
    ) -> TesterOutput:
        total  = len(results)
        passed = sum(1 for r in results if r.passed)

        print("\n" + "=" * 60)
        print("  ✅ ALL TESTS PASSED")
        print("=" * 60)
        print(f"  Project      : {project_name}")
        print(f"  Workspace ID : {workspace_id}")
        print(f"  Tests Passed : {passed}/{total}")
        print("-" * 60)
        for r in results:
            icon = "✅" if r.passed else "❌"
            print(f"  {icon} [{r.exit_code}] {r.command}  ({r.duration_ms}ms)")
        print("=" * 60)
        print("\n📤 Sending verified payload to Agent 5 (Security Agent)...")
        print("   [Agent 5 not yet implemented — stub handoff below]\n")
        print("📁 Developer bundle paths available to Agent 5:")
        for file_path in deployer_output.deployed_files:
            print(f"   - {file_path}")

        handoff_payload = {
            "project_name"   : project_name,
            "workspace_id"   : workspace_id,
            "language"       : deployer_output.language,
            "entrypoint_file": deployer_output.entrypoint_file,
            "deployed_files" : deployer_output.deployed_files,
            "env_vars"       : deployer_output.env_vars,
            "test_summary"   : {
                "total": total,
                "passed": passed,
                "failed": 0,
            },
        }

        logger.info(f"[→ Agent 5] Handoff payload: {json.dumps(handoff_payload, indent=2)}")

        raw_logs = "\n".join(
            f"$ {result.command}\n{result.stdout}\n{result.stderr}" for result in results
        )
        test_report = TestReport(
            sandbox_id=workspace_id,
            execution_duration_ms=round(sum(result.duration_ms or 0 for result in results), 2),
            summary={"total_tools": total, "passed_count": passed, "failed_count": 0},
            tool_results=[
                ToolResult(
                    tool_name=result.command,
                    status="PASS",
                    latency_ms=result.duration_ms,
                    response_sample=result.stdout[:1000],
                )
                for result in results
            ],
            raw_logs=raw_logs,
        )

        return TesterOutput(
            workspace_id=workspace_id,
            project_name=project_name,
            status="TESTS_PASSED",
            handoff_payload=handoff_payload,
            test_report=test_report,
        )

    # ─────────────────────────────────────────────
    #  Failure path → Agent 1 (Planner)
    # ─────────────────────────────────────────────
    def _handle_failure(
        self,
        workspace_id: str,
        project_name: str,
        results: list,
        total: int,
        passed: int,
        failed: int,
        test_protocol: Optional[dict],
    ) -> TesterOutput:

        # ── Parse logs for intelligence ──
        failure_locations, root_cause, suggestions = LogParser.parse(results)

        # ── Build failed_cases list ──
        failed_cases = [
            {
                "command"  : r.command,
                "exit_code": r.exit_code,
                "stdout"   : r.stdout[:1000],
                "stderr"   : r.stderr[:1000],
            }
            for r in results if not r.passed
        ]

        # ── Build DiagnosticReport ──
        report = DiagnosticReport(
            report_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            project_name=project_name,
            workspace_id=workspace_id,
            total_tests=total,
            passed_tests=passed,
            failed_tests=failed,
            failed_cases=failed_cases,
            failure_locations=failure_locations,
            root_cause_summary=root_cause,
            suggestions=suggestions,
            raw_results=results,
            overall_status="FAIL",
        )

        feedback = self._build_feedback_report(
            workspace_id=workspace_id,
            results=results,
            root_cause=root_cause,
            suggestions=suggestions,
            test_protocol=test_protocol,
        )

        # ── Save JSON report to disk ──
        report_path = self._save_report(report)
        feedback_path = self._save_feedback_report(feedback)

        # ── Print diagnostic summary ──
        print("\n" + "=" * 60)
        print("  ❌ TESTS FAILED — Diagnostic Report Generated")
        print("=" * 60)
        print(f"  Project        : {project_name}")
        print(f"  Workspace ID   : {workspace_id}")
        print(f"  Tests          : {passed} passed / {failed} failed / {total} total")
        print(f"  Root Cause     : {root_cause}")
        print(f"  Failure Locs   : {', '.join(failure_locations)}")
        print(f"  Suggestions    ({len(suggestions)}):")
        for i, s in enumerate(suggestions, 1):
            print(f"    {i}. {s}")
        print(f"\n  📄 Report saved → {report_path}")
        print("=" * 60)

        # ── Pretty-print shared feedback JSON for Planner Agent ──
        print("\n📤 Sending feedback report to Agent 1 (Planner Agent)...")
        print("   [Agent 1 not yet implemented — feedback JSON below]\n")
        print(json.dumps(feedback.model_dump(), indent=2, default=str))
        print()

        logger.warning(
            f"[→ Agent 1 (Planner)] DiagnosticReport ID={report.report_id} "
            f"— {failed}/{total} tests failed. Feedback at: {feedback_path}"
        )

        return TesterOutput(
            workspace_id=workspace_id,
            project_name=project_name,
            status="TESTS_FAILED",
            diagnostic_report=report,
            feedback_report=feedback,
        )

    # ─────────────────────────────────────────────
    #  Helpers
    # ─────────────────────────────────────────────
    def _save_report(self, report: DiagnosticReport) -> str:
        """Persists the diagnostic report as a JSON file and returns its path."""
        import os
        filename = f"diagnostic_{report.report_id[:8]}_{report.project_name}.json"
        path = os.path.join(self.report_output_dir, filename)

        # Exclude heavy raw_results from saved JSON (full data stays in memory)
        report_dict = report.model_dump(exclude={"raw_results"})
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report_dict, f, indent=2, default=str)

        logger.info(f"Diagnostic report saved: {path}")
        return path

    def _save_feedback_report(self, feedback: FeedbackReport) -> str:
        """Persist the shared self-healing feedback JSON contract."""
        import os
        filename = f"feedback_{feedback.sandbox_id}.json"
        path = os.path.join(self.report_output_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(feedback.model_dump(), f, indent=2)
        logger.info(f"Feedback report saved: {path}")
        return path

    @staticmethod
    def _build_feedback_report(
        workspace_id: str,
        results: list,
        root_cause: str,
        suggestions: list,
        test_protocol: Optional[dict],
    ) -> FeedbackReport:
        """Map a failed command into the shared FEEDBACK_CONTRACT schema."""
        failed_result = next(result for result in results if not result.passed)
        combined_logs = f"{failed_result.stderr}\n{failed_result.stdout}"
        if "SyntaxError" in combined_logs:
            category = "syntax_error"
        elif "HTTP" in combined_logs or "httpx." in combined_logs:
            category = "http_status_error"
        elif "ValidationError" in combined_logs or "validation" in combined_logs.lower():
            category = "type_validation_error"
        else:
            category = "runtime_crash"

        test = ((test_protocol or {}).get("tests") or [{}])[0]
        return FeedbackReport(
            sandbox_id=workspace_id,
            failing_tool=test.get("tool_name", failed_result.command),
            error_category=category,
            tested_payload=test.get("test_payload", {}),
            error_message=root_cause,
            traceback=failed_result.stderr or failed_result.stdout,
            suggested_fix=(suggestions[0] if suggestions else "Inspect the sandbox logs and correct the failing tool."),
        )

    def _cleanup_sandbox(self, sandbox_mgr, workspace_id: str) -> None:
        """Destroys the Daytona sandbox workspace — always called after testing."""
        if sandbox_mgr is None or workspace_id == "NONE":
            logger.warning("No sandbox handle available — skipping cleanup.")
            return
        try:
            logger.info(f"🧹 Cleaning up sandbox: {workspace_id}")
            sandbox_mgr.destroy_workspace(workspace_id)
            print(f"\n🧹 Sandbox [{workspace_id}] deleted from Daytona Cloud.\n")
        except Exception as exc:
            logger.error(f"Failed to destroy sandbox {workspace_id}: {exc}")
