"""
Tester Agent - Log Parser & Diagnostic Analyser (Agent 4)
Analyses raw test results to extract failure locations, root cause,
and ordered actionable suggestions for the Planner Agent.
"""
import re
import logging
from typing import List, Tuple

from .schemas import TestCommandResult

logger = logging.getLogger("TesterAgent.LogParser")


# ──────────────────────────────────────────────────────────
#  Pattern library for common Python/Node failure signatures
# ──────────────────────────────────────────────────────────
_PY_TRACEBACK_FILE = re.compile(
    r'File "(?P<file>[^"]+)", line (?P<line>\d+)'
)
_PY_ASSERT_ERROR   = re.compile(r'AssertionError')
_PY_IMPORT_ERROR   = re.compile(r'(ModuleNotFoundError|ImportError): (.+)')
_PY_SYNTAX_ERROR   = re.compile(r'SyntaxError: (.+)')
_PY_TIMEOUT        = re.compile(r'timed out', re.IGNORECASE)
_NODE_ERROR        = re.compile(r'Error: (.+)')
_TEST_PASS_PATTERN = re.compile(r'\[TEST PASS\]|\bPASSED\b|ok\b', re.IGNORECASE)


class LogParser:
    """
    Parses raw stdout/stderr from failed test runs to produce:
    - failure_locations  : list of "file.py:line" strings
    - root_cause_summary : single concise sentence
    - suggestions        : prioritised list of fix advice
    """

    @staticmethod
    def parse(results: List[TestCommandResult]) -> Tuple[List[str], str, List[str]]:
        """
        Returns: (failure_locations, root_cause_summary, suggestions)
        """
        failure_locations: List[str] = []
        suggestions: List[str] = []
        root_cause_parts: List[str] = []

        failed = [r for r in results if not r.passed]

        for result in failed:
            combined = (result.stderr or "") + "\n" + (result.stdout or "")

            # ── Extract file:line locations from tracebacks ──
            for m in _PY_TRACEBACK_FILE.finditer(combined):
                loc = f"{m.group('file')}:{m.group('line')}"
                if loc not in failure_locations:
                    failure_locations.append(loc)

            # ── Classify root cause ──
            if _PY_IMPORT_ERROR.search(combined):
                mod_match = _PY_IMPORT_ERROR.search(combined)
                mod_name = mod_match.group(2).strip() if mod_match else "unknown module"
                root_cause_parts.append(f"Missing dependency: {mod_name}")
                suggestions.append(
                    f"Add '{mod_name}' to requirements.txt and re-run setup.sh"
                )
                suggestions.append(
                    "Verify that setup.sh runs 'pip install -r requirements.txt' "
                    "before executing tests."
                )

            elif _PY_SYNTAX_ERROR.search(combined):
                syn_match = _PY_SYNTAX_ERROR.search(combined)
                detail = syn_match.group(1) if syn_match else ""
                root_cause_parts.append(f"Syntax error in generated code: {detail}")
                suggestions.append(
                    "Review the generated source file for syntax issues "
                    "(missing colons, brackets, indentation)."
                )
                suggestions.append(
                    "Ask Coder Agent to re-generate and lint the file before deployment."
                )

            elif _PY_ASSERT_ERROR.search(combined):
                root_cause_parts.append(
                    "An assertion in a test function evaluated to False."
                )
                suggestions.append(
                    "Review the test logic in test_server.py — "
                    "check expected vs. actual return values."
                )
                suggestions.append(
                    "Ensure the MCP server functions return the exact types and "
                    "values the tests expect."
                )

            elif _PY_TIMEOUT.search(combined):
                root_cause_parts.append(
                    "Command execution timed out — server likely hung or entered "
                    "an infinite loop."
                )
                suggestions.append(
                    "Add a startup timeout / health-check flag to the server entrypoint."
                )
                suggestions.append(
                    "Check for blocking I/O or missing asyncio event loop handling."
                )

            elif result.exit_code != 0:
                # Generic non-zero exit
                root_cause_parts.append(
                    f"Command '{result.command}' exited with code {result.exit_code}."
                )
                suggestions.append(
                    f"Inspect stderr for command '{result.command}': "
                    f"{result.stderr[:200]}"
                )
                suggestions.append(
                    "Verify the test command path and that all dependencies "
                    "are installed in the sandbox."
                )

        # Deduplicate suggestions preserving order
        seen = set()
        deduped: List[str] = []
        for s in suggestions:
            if s not in seen:
                seen.add(s)
                deduped.append(s)

        root_cause = (
            "; ".join(root_cause_parts)
            if root_cause_parts
            else "Unknown failure — review raw logs."
        )

        if not failure_locations:
            failure_locations = ["<unknown> — no traceback found in output"]

        logger.info(f"Parsed {len(failed)} failure(s). Root cause: {root_cause}")
        return failure_locations, root_cause, deduped
