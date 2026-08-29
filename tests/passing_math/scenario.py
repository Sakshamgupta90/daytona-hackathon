from deployment_stage.deployer_agent.schemas import CodeFile, CoderOutput


CODER_OUTPUT = CoderOutput(
    project_name="math-mcp-server",
    language="python",
    runtime_version="3.11",
    entrypoint_file="server.py",
    env_vars={"APP_ENV": "test"},
    files=[
        CodeFile(path="requirements.txt", content="# No external dependencies required\n"),
        CodeFile(
            path="server.py",
            content=(
                "def add(a, b): return a + b\n"
                "def subtract(a, b): return a - b\n"
                "def multiply(a, b): return a * b\n"
                "def divide(a, b):\n"
                "    if b == 0:\n"
                "        raise ValueError('Division by zero is not allowed.')\n"
                "    return a / b\n"
            ),
        ),
        CodeFile(
            path="test_server.py",
            content=(
                "import importlib.util\n"
                "spec = importlib.util.spec_from_file_location('server', 'server.py')\n"
                "server = importlib.util.module_from_spec(spec)\n"
                "spec.loader.exec_module(server)\n"
                "assert server.add(3, 4) == 7\n"
                "assert server.subtract(10, 3) == 7\n"
                "assert server.multiply(6, 7) == 42\n"
                "assert server.divide(10, 2) == 5\n"
                "try:\n"
                "    server.divide(1, 0)\n"
                "    raise AssertionError('Expected ValueError')\n"
                "except ValueError:\n"
                "    pass\n"
                "print('[ALL TESTS PASSED]')\n"
            ),
        ),
    ],
    test_commands=["python3 test_server.py"],
)

EXPECTED_STATUS = "TESTS_PASSED"
