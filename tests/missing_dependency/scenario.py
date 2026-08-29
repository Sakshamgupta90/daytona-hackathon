from deployment_stage.deployer_agent.schemas import CodeFile, CoderOutput


CODER_OUTPUT = CoderOutput(
    project_name="missing-dependency-mcp-server",
    language="python",
    runtime_version="3.11",
    entrypoint_file="server.py",
    env_vars={},
    files=[
        CodeFile(path="requirements.txt", content="# intentionally empty\n"),
        CodeFile(path="server.py", content="import mcp_nonexistent_lib_xyz\n"),
        CodeFile(
            path="test_server.py",
            content=(
                "import importlib.util\n"
                "spec = importlib.util.spec_from_file_location('server', 'server.py')\n"
                "server = importlib.util.module_from_spec(spec)\n"
                "spec.loader.exec_module(server)\n"
            ),
        ),
    ],
    test_commands=["python3 test_server.py"],
)

EXPECTED_STATUS = "TESTS_FAILED"
