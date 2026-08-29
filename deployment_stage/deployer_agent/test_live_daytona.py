"""
Live Daytona Cloud Integration Test
Reads credentials from .env and creates a real Daytona sandbox,
uploads a sample MCP server, runs setup, and verifies the sandbox is live.
"""
import logging
import os

# Load .env before anything else
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s"
)

try:
    from deployment_stage.deployer_agent.schemas import CoderOutput, CodeFile
    from deployment_stage.deployer_agent.deployer import DeployerAgent
except ImportError:
    from schemas import CoderOutput, CodeFile
    from deployer import DeployerAgent


def test_live_daytona():
    print("\n" + "=" * 55)
    print("  DAYTONA CLOUD LIVE DEPLOYMENT TEST")
    print("=" * 55)

    mode = os.getenv("MOCK_SANDBOX", "true")
    print(f"\n📦 Sandbox Mode: {'LOCAL MOCK' if mode.lower() in ('true','1','yes') else '🌍 DAYTONA CLOUD LIVE'}")
    print(f"🌍 Target Region: {os.getenv('DAYTONA_TARGET', 'eu').upper()}")

    # Simulated Coder Agent output - a lightweight echo MCP server
    coder_output = CoderOutput(
        project_name="echo-mcp-server",
        language="python",
        runtime_version="3.11",
        entrypoint_file="server.py",
        files=[
            CodeFile(
                path="requirements.txt",
                content="# Minimal dependencies for echo server test\n"
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
                    "    print(f'[TEST PASS] echo_tool: {result}')\n"
                    "\n"
                    "def test_server_import():\n"
                    "    import importlib.util\n"
                    "    spec = importlib.util.spec_from_file_location('server', 'server.py')\n"
                    "    assert spec is not None\n"
                    "    print('[TEST PASS] server.py importable')\n"
                    "\n"
                    "if __name__ == '__main__':\n"
                    "    test_echo_tool()\n"
                    "    test_server_import()\n"
                    "    print('[ALL TESTS PASSED]')\n"
                )
            ),
        ],
        env_vars={"LOG_LEVEL": "DEBUG", "ENV": "test"},
        test_commands=["python3 test_server.py"]
    )

    print(f"\n📁 Project:   {coder_output.project_name}")
    print(f"🐍 Language:  {coder_output.language} {coder_output.runtime_version}")
    print(f"📄 Files:     {[f.path for f in coder_output.files]}")
    print(f"🧪 Tests:     {coder_output.test_commands}")

    # Run Deployer Agent
    print("\n▶ Starting Deployer Agent...")
    agent = DeployerAgent()
    result = agent.deploy(coder_output)

    # Print Results
    print("\n" + "-" * 55)
    print(f"  Deployment Status : {result.status}")
    print(f"  Workspace ID      : {result.workspace_id}")
    print(f"  Uploaded Files    : {result.deployed_files}")
    print(f"  Test Commands     : {result.test_commands}")
    if result.error_message:
        print(f"  ❌ Error          : {result.error_message}")
    print("-" * 55)

    # Verify success
    assert result.status == "DEPLOYED", (
        f"Expected DEPLOYED but got {result.status}\n"
        f"Error: {result.error_message}"
    )

    print("\n✅ Deployer Agent: Sandbox Created & Ready!")

    # Tell user how to view on Daytona dashboard
    if os.getenv("MOCK_SANDBOX", "true").lower() not in ("true", "1", "yes"):
        print(f"\n🔍 View your LIVE sandbox on Daytona Cloud:")
        print(f"   → Open https://app.daytona.io")
        print(f"   → Click 'Sandboxes' in the left sidebar")
        print(f"   → Look for Sandbox ID: {result.workspace_id}")
        print(f"\n⚠️  Sandbox is LEFT ALIVE intentionally for inspection.")
        print(f"    To delete it manually: go to the dashboard and click Delete.")

    # NOTE: Cleanup is intentionally skipped so sandbox is visible on Daytona dashboard.
    # Uncomment the lines below to enable auto-cleanup after inspection:
    # if result.raw_workspace_handle and result.workspace_id != "NONE":
    #     result.raw_workspace_handle.destroy_workspace(result.workspace_id)
    #     print(f"\n🧹 Sandbox {result.workspace_id} cleaned up successfully.")

    print("\n✅ Deployment test complete!\n")


if __name__ == "__main__":
    test_live_daytona()
