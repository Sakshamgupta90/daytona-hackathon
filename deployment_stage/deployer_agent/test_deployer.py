try:
    from deployment_stage.deployer_agent.schemas import CoderOutput, CodeFile
    from deployment_stage.deployer_agent.deployer import DeployerAgent
except ImportError:
    from schemas import CoderOutput, CodeFile
    from deployer import DeployerAgent


def test_deployer_mock_run():
    print("=== Testing Deployer Agent (Mock Sandbox Mode) ===")

    # 1. Simulate Coder Agent output for a Weather MCP Server
    coder_output = CoderOutput(
        project_name="weather-mcp-server",
        language="python",
        runtime_version="3.11",
        entrypoint_file="server.py",
        files=[
            CodeFile(
                path="requirements.txt",
                content="# Local mock test - zero external dependencies\n"
            ),
            CodeFile(
                path="server.py",
                content=(
                    "import sys\n"
                    "print('Weather MCP Server running...')\n"
                )
            ),
            CodeFile(
                path="test_server.py",
                content=(
                    "def test_weather():\n"
                    "    assert 1 + 1 == 2\n"
                )
            )
        ],
        env_vars={"API_KEY": "test_secret_123"},
        test_commands=["python3 test_server.py"]
    )

    # 2. Instantiate Deployer Agent and deploy
    agent = DeployerAgent()
    result = agent.deploy(coder_output)

    # 3. Print Results
    print(f"\nDeployment Status: {result.status}")
    print(f"Workspace ID:       {result.workspace_id}")
    print(f"Uploaded Files:     {result.deployed_files}")
    print(f"Test Commands:      {result.test_commands}")

    assert result.status == "DEPLOYED", f"Expected DEPLOYED but got {result.status}"
    print("\n✅ Deployer Agent Test Passed Successfully!")

    # 4. Clean up mock workspace
    if result.raw_workspace_handle and result.workspace_id != "NONE":
        result.raw_workspace_handle.destroy_workspace(result.workspace_id)
        print("🧹 Cleaned up sandbox workspace successfully.")


if __name__ == "__main__":
    test_deployer_mock_run()
