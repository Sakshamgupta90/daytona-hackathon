from deployment_stage.deployer_agent.schemas import CodeFile, CoderOutput


CODER_OUTPUT = CoderOutput(
    project_name="buggy-math-mcp-server",
    language="python",
    runtime_version="3.11",
    entrypoint_file="server.py",
    env_vars={"APP_ENV": "test"},
    files=[
        CodeFile(path="requirements.txt", content="# No external dependencies\n"),
        CodeFile(path="server.py", content="def add(a, b): return a - b  # intentional bug\n"),
        CodeFile(
            path="test_server.py",
            content=(
                "import importlib.util\n"
                "spec = importlib.util.spec_from_file_location('server', 'server.py')\n"
                "server = importlib.util.module_from_spec(spec)\n"
                "spec.loader.exec_module(server)\n"
                "assert server.add(3, 4) == 7, 'add() returned the wrong value'\n"
            ),
        ),
    ],
    test_commands=["python3 test_server.py"],
)

EXPECTED_STATUS = "TESTS_FAILED"
