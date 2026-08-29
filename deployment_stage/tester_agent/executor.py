"""
Tester Agent - Executor (Agent 4)
Runs all test_commands inside the active Daytona sandbox workspace
and collects raw stdout/stderr/exit_code for each command.
"""
import logging
import time
from typing import List

from .schemas import TestCommandResult

logger = logging.getLogger("TesterAgent.Executor")


class SandboxTestExecutor:
    """
    Executes a list of test commands inside the active Daytona sandbox
    and returns structured per-command results.
    """

    def __init__(self, sandbox_manager, workspace_id: str):
        """
        Args:
            sandbox_manager: Active BaseSandboxManager instance (Daytona or Mock)
            workspace_id:    The provisioned sandbox workspace ID from Deployer Agent
        """
        self.sandbox_manager = sandbox_manager
        self.workspace_id = workspace_id

    def run_all(self, test_commands: List[str]) -> List[TestCommandResult]:
        """
        Runs each test command sequentially inside the sandbox.
        Returns a list of TestCommandResult for each command.
        """
        results: List[TestCommandResult] = []

        if not test_commands:
            logger.warning("No test commands provided — nothing to execute.")
            return results

        logger.info(
            f"Running {len(test_commands)} test command(s) "
            f"in sandbox [{self.workspace_id}]"
        )

        for cmd in test_commands:
            logger.info(f"  ▶ Executing: {cmd}")
            start_ms = time.time() * 1000

            raw = self.sandbox_manager.exec_command(self.workspace_id, cmd)

            duration_ms = (time.time() * 1000) - start_ms
            passed = raw.get("exit_code", 1) == 0

            result = TestCommandResult(
                command=cmd,
                exit_code=raw.get("exit_code", 1),
                stdout=raw.get("stdout", ""),
                stderr=raw.get("stderr", ""),
                passed=passed,
                duration_ms=round(duration_ms, 2),
            )

            status_icon = "✅" if passed else "❌"
            logger.info(
                f"  {status_icon} '{cmd}' → exit_code={result.exit_code} "
                f"({result.duration_ms}ms)"
            )
            if not passed:
                logger.warning(f"  stderr: {result.stderr[:300]}")

            results.append(result)

        total = len(results)
        passed_count = sum(1 for r in results if r.passed)
        logger.info(
            f"Execution complete: {passed_count}/{total} commands passed."
        )
        return results
