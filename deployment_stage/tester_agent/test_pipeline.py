"""
End-to-End Pipeline Test: Deployer Agent → Tester Agent
=========================================================
Runs Agent 3 (Deployer) to deploy a sample MCP server to Daytona Cloud,
then hands the active workspace to Agent 4 (Tester) which:
  - Executes all test commands inside the sandbox
  - Routes to Agent 5 (Security) on success  [stub print]
  - Routes diagnostic JSON to Agent 1 (Planner) on failure [stub print]
  - Deletes the sandbox workspace after evaluation
"""
import logging
import os
import sys

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    stream=sys.stdout,
)

# ── Imports ──────────────────────────────────────────────
try:
    from deployment_stage.deployer_agent.schemas import CoderOutput, CodeFile
    from deployment_stage.deployer_agent.deployer import DeployerAgent
    from deployment_stage.tester_agent.tester import TesterAgent
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    from deployment_stage.deployer_agent.schemas import CoderOutput, CodeFile
    from deployment_stage.deployer_agent.deployer import DeployerAgent
    from deployment_stage.tester_agent.tester import TesterAgent


# ═══════════════════════════════════════════════════════════
#  Sample MCP server payload (simulates Coder Agent output)
# ═══════════════════════════════════════════════════════════

# ── Scenario A: PASSING server ──────────────────────────────
PASSING_CODER_OUTPUT = CoderOutput(
    project_name="echo-mcp-server",
    language="python",
    runtime_version="3.11",
    entrypoint_file="server.py",
    files=[
        CodeFile(
            path="requirements.txt",
            content="# No external deps needed for echo server\n"
        ),
        CodeFile(
            path="server.py",
            content=(
                "print('[MCP Echo Server] Initializing...')\n"
                "print('[MCP Echo Server] Tools: [echo]')\n"
                "print('[MCP Echo Server] Status: READY')\n"
            )
        ),
        CodeFile(
            path="test_server.py",
            content=(
                "def test_echo_tool():\n"
                "    result = 'hello world'\n"
                "    assert result == 'hello world'\n"
                "    print(f'[TEST PASS] echo_tool returned: {result}')\n"
                "\n"
                "def test_server_import():\n"
                "    import importlib.util\n"
                "    spec = importlib.util.spec_from_file_location('server', 'server.py')\n"
                "    assert spec is not None\n"
                "    print('[TEST PASS] server.py is importable')\n"
                "\n"
                "if __name__ == '__main__':\n"
                "    test_echo_tool()\n"
                "    test_server_import()\n"
                "    print('[ALL TESTS PASSED]')\n"
            )
        ),
    ],
    env_vars={"LOG_LEVEL": "DEBUG", "ENV": "test"},
    test_commands=["python3 test_server.py"],
)

# ── Scenario B: FAILING server (assertion error) ────────────
FAILING_CODER_OUTPUT = CoderOutput(
    project_name="broken-mcp-server",
    language="python",
    runtime_version="3.11",
    entrypoint_file="server.py",
    files=[
        CodeFile(path="requirements.txt", content="# no deps\n"),
        CodeFile(
            path="server.py",
            content=(
                "print('[MCP Server] Starting...')\n"
                "def get_answer(): return 41  # bug: should be 42\n"
            )
        ),
        CodeFile(
            path="test_server.py",
            content=(
                "import importlib.util, sys\n"
                "spec = importlib.util.spec_from_file_location('server', 'server.py')\n"
                "mod = importlib.util.module_from_spec(spec)\n"
                "spec.loader.exec_module(mod)\n"
                "\n"
                "def test_answer():\n"
                "    result = mod.get_answer()\n"
                "    assert result == 42, f'Expected 42 but got {result}'\n"
                "    print('[TEST PASS] get_answer == 42')\n"
                "\n"
                "if __name__ == '__main__':\n"
                "    test_answer()\n"
                "    print('[ALL TESTS PASSED]')\n"
            )
        ),
    ],
    env_vars={},
    test_commands=["python3 test_server.py"],
)


# ═══════════════════════════════════════════════════════════
#  Main runner
# ═══════════════════════════════════════════════════════════
def run_pipeline(coder_output: CoderOutput, label: str) -> None:
    print("\n" + "█" * 60)
    print(f"  PIPELINE TEST: {label}")
    print("█" * 60)

    # ── Phase 1: Deploy ─────────────────────────────────────
    print("\n▶ Phase 1 — Deployer Agent (Agent 3)")
    deployer = DeployerAgent()
    deployer_output = deployer.deploy(coder_output)

    if deployer_output.status != "DEPLOYED":
        print(f"\n❌ Deployment failed: {deployer_output.error_message}")
        return

    print(f"  ✅ Deployed  →  Workspace ID: {deployer_output.workspace_id}")

    # ── Phase 2: Test ───────────────────────────────────────
    print("\n▶ Phase 2 — Tester Agent (Agent 4)")
    tester = TesterAgent(report_output_dir="./tester_reports")
    tester_output = tester.run(deployer_output)

    # ── Final Status ────────────────────────────────────────
    print("\n" + "─" * 60)
    print(f"  Pipeline result : {tester_output.status}")
    print(f"  Project         : {tester_output.project_name}")
    print("─" * 60 + "\n")


if __name__ == "__main__":
    mode = os.getenv("MOCK_SANDBOX", "true")
    is_mock = mode.lower() in ("true", "1", "yes")

    print("\n" + "=" * 60)
    print("  MCP FORGE — DEPLOYER + TESTER PIPELINE TEST")
    print("=" * 60)
    print(f"  Sandbox Mode : {'LOCAL MOCK' if is_mock else '🌍 DAYTONA CLOUD LIVE'}")
    print(f"  Region       : {os.getenv('DAYTONA_TARGET', 'eu').upper()}")

    # ── Run Scenario A: should PASS ──
    run_pipeline(PASSING_CODER_OUTPUT, label="Scenario A — PASSING server")

    # ── Run Scenario B: should FAIL with diagnostic ──
    run_pipeline(FAILING_CODER_OUTPUT, label="Scenario B — FAILING server (assertion)")
