"""
Tester Agent - Schemas (Agent 4)
Data contracts for test execution results, diagnostic reports, and handoff payloads.
"""
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime


class TestCommandResult(BaseModel):
    """Result of a single test command executed inside the Daytona sandbox."""
    command: str = Field(..., description="The exact command that was run")
    exit_code: int = Field(..., description="Process exit code (0 = pass, non-zero = fail)")
    stdout: str = Field(default="", description="Standard output from the command")
    stderr: str = Field(default="", description="Standard error output from the command")
    passed: bool = Field(..., description="True if exit_code == 0")
    duration_ms: Optional[float] = Field(default=None, description="Execution time in milliseconds")


class DiagnosticReport(BaseModel):
    """
    Structured failure report sent to Agent 1 (Planner) when tests fail.
    Contains full context, logs, failure locations, and actionable suggestions.
    """
    report_id: str = Field(..., description="Unique ID for this diagnostic report")
    timestamp: str = Field(..., description="ISO timestamp when report was generated")
    project_name: str = Field(..., description="Name of the project that failed")
    workspace_id: str = Field(..., description="Daytona sandbox workspace ID")

    # Test summary
    total_tests: int = Field(..., description="Total number of test commands attempted")
    passed_tests: int = Field(..., description="Number of test commands that passed")
    failed_tests: int = Field(..., description="Number of test commands that failed")

    # Failure details
    failed_cases: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of failed test cases with command, stderr, stdout, and exit code"
    )

    # Actionable intelligence
    failure_locations: List[str] = Field(
        default_factory=list,
        description="Best-guess file/function locations where the failure occurred"
    )
    root_cause_summary: str = Field(
        default="",
        description="Human-readable summary of the probable root cause"
    )
    suggestions: List[str] = Field(
        default_factory=list,
        description="Ordered list of actionable suggestions to fix the failures"
    )

    # Full raw logs
    raw_results: List[TestCommandResult] = Field(
        default_factory=list,
        description="Complete raw results from all test command executions"
    )

    # Status
    overall_status: str = Field(
        ...,
        description="PASS or FAIL"
    )


class ToolResult(BaseModel):
    """One tool execution in the Person 2 TestReport contract."""

    tool_name: str
    status: str
    latency_ms: Optional[float] = None
    response_sample: str = ""
    error: Optional[str] = None


class TestReport(BaseModel):
    """Success contract emitted by Agent 4 to the Security/UI stage."""

    status: str = "PASS"
    stage: str = "functional_testing"
    sandbox_id: str
    execution_duration_ms: float
    summary: Dict[str, int]
    tool_results: List[ToolResult]
    raw_logs: str


class FeedbackReport(BaseModel):
    """Unified self-healing feedback contract shared with Persons 1 and 3."""

    status: str = "FAIL"
    stage: str = "functional_test"
    sandbox_id: str
    failing_tool: str
    error_category: str
    tested_payload: Dict[str, Any] = Field(default_factory=dict)
    error_message: str
    traceback: str
    suggested_fix: str


class TesterOutput(BaseModel):
    """
    Final output from Tester Agent (Agent 4).
    On SUCCESS → routes to Agent 5 (Security).
    On FAIL → routes diagnostic report to Agent 1 (Planner).
    """
    model_config = {"arbitrary_types_allowed": True}

    workspace_id: str
    project_name: str
    status: str  # "TESTS_PASSED" | "TESTS_FAILED"
    diagnostic_report: Optional[DiagnosticReport] = None
    feedback_report: Optional[FeedbackReport] = None
    test_report: Optional[TestReport] = None
    handoff_payload: Optional[Dict[str, Any]] = None  # Payload for Agent 5 (Security)
    error_message: Optional[str] = None
