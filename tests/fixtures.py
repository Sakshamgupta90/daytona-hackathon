"""
Test Fixtures — Simulated Coder Agent (Agent 2) outputs
========================================================
Each fixture is a CoderOutput object that the Deployer Agent accepts.

Fixtures:
  PASSING_MATH_SERVER   — A correct calculator MCP server. All tests pass.
  FAILING_MATH_SERVER   — A buggy calculator MCP server. Tests fail with AssertionError.
  FAILING_IMPORT_SERVER — A server with a missing dependency. Tests fail with ImportError.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from deployment_stage.deployer_agent.schemas import CoderOutput, CodeFile


# ═══════════════════════════════════════════════════════════
#  FIXTURE 1 — PASSING: correct calculator MCP server
# ═══════════════════════════════════════════════════════════
PASSING_MATH_SERVER = CoderOutput(
    project_name="math-mcp-server",
    language="python",
    runtime_version="3.11",
    entrypoint_file="server.py",
    env_vars={"APP_ENV": "test"},
    files=[
        # ── requirements.txt ──────────────────────────────────
        CodeFile(
            path="requirements.txt",
            content="# No external dependencies required\n"
        ),

        # ── server.py — the MCP calculator tool ───────────────
        CodeFile(
            path="server.py",
            content="""\
\"\"\"
MCP Math Server
Exposes a basic calculator as an MCP tool.
\"\"\"

def add(a: float, b: float) -> float:
    \"\"\"Add two numbers.\"\"\"
    return a + b

def subtract(a: float, b: float) -> float:
    \"\"\"Subtract b from a.\"\"\"
    return a - b

def multiply(a: float, b: float) -> float:
    \"\"\"Multiply two numbers.\"\"\"
    return a * b

def divide(a: float, b: float) -> float:
    \"\"\"Divide a by b. Raises ValueError on division by zero.\"\"\"
    if b == 0:
        raise ValueError("Division by zero is not allowed.")
    return a / b

if __name__ == "__main__":
    print("[MCP Math Server] Initializing...")
    print("[MCP Math Server] Tools: [add, subtract, multiply, divide]")
    print("[MCP Math Server] Status: READY")
"""
        ),

        # ── test_server.py — full test suite ──────────────────
        CodeFile(
            path="test_server.py",
            content="""\
\"\"\"
Test suite for MCP Math Server.
All assertions are correct — this fixture should PASS.
\"\"\"
import importlib.util, sys

# Dynamically load server.py from the sandbox workspace
spec = importlib.util.spec_from_file_location("server", "server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


def test_add():
    assert server.add(3, 4) == 7,   f"Expected 7, got {server.add(3, 4)}"
    assert server.add(-1, 1) == 0,  f"Expected 0, got {server.add(-1, 1)}"
    assert server.add(100, 200) == 300, f"Expected 300, got {server.add(100, 200)}"
    print("[TEST PASS] add()")

def test_subtract():
    assert server.subtract(10, 3) == 7,  f"Expected 7, got {server.subtract(10, 3)}"
    assert server.subtract(0, 5)  == -5, f"Expected -5, got {server.subtract(0, 5)}"
    print("[TEST PASS] subtract()")

def test_multiply():
    assert server.multiply(6, 7) == 42,  f"Expected 42, got {server.multiply(6, 7)}"
    assert server.multiply(0, 99) == 0,  f"Expected 0, got {server.multiply(0, 99)}"
    print("[TEST PASS] multiply()")

def test_divide():
    assert server.divide(10, 2) == 5.0, f"Expected 5.0, got {server.divide(10, 2)}"
    assert server.divide(7, 2)  == 3.5, f"Expected 3.5, got {server.divide(7, 2)}"
    print("[TEST PASS] divide()")

def test_divide_by_zero():
    try:
        server.divide(1, 0)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "zero" in str(e).lower()
        print("[TEST PASS] divide_by_zero raises ValueError correctly")

def test_server_importable():
    assert spec is not None, "server.py spec should not be None"
    print("[TEST PASS] server.py is importable")

if __name__ == "__main__":
    test_add()
    test_subtract()
    test_multiply()
    test_divide()
    test_divide_by_zero()
    test_server_importable()
    print("")
    print("╔══════════════════════════════════╗")
    print("║   ALL 6 TESTS PASSED             ║")
    print("╚══════════════════════════════════╝")
"""
        ),
    ],
    test_commands=["python3 test_server.py"],
)


# ═══════════════════════════════════════════════════════════
#  FIXTURE 2 — FAILING: buggy calculator (wrong return values)
# ═══════════════════════════════════════════════════════════
FAILING_MATH_SERVER = CoderOutput(
    project_name="buggy-math-mcp-server",
    language="python",
    runtime_version="3.11",
    entrypoint_file="server.py",
    env_vars={"APP_ENV": "test"},
    files=[
        CodeFile(
            path="requirements.txt",
            content="# No external dependencies\n"
        ),

        # ── server.py — intentional bugs ──────────────────────
        CodeFile(
            path="server.py",
            content="""\
\"\"\"
Buggy MCP Math Server
Contains intentional logic errors for testing the failure path.
\"\"\"

def add(a: float, b: float) -> float:
    return a - b          # BUG: should be a + b

def subtract(a: float, b: float) -> float:
    return a + b          # BUG: should be a - b

def multiply(a: float, b: float) -> float:
    return a * b          # correct

def divide(a: float, b: float) -> float:
    return a / b          # missing zero-guard BUG

if __name__ == "__main__":
    print("[Buggy MCP Math Server] Starting (with bugs)...")
"""
        ),

        # ── test_server.py — correct assertions catch the bugs ─
        CodeFile(
            path="test_server.py",
            content="""\
\"\"\"
Test suite for MCP Math Server.
Correct assertions — will FAIL against the buggy server.py.
\"\"\"
import importlib.util

spec = importlib.util.spec_from_file_location("server", "server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


def test_add():
    result = server.add(3, 4)
    assert result == 7, f"add(3, 4) expected 7 but got {result}"
    print("[TEST PASS] add()")

def test_subtract():
    result = server.subtract(10, 3)
    assert result == 7, f"subtract(10, 3) expected 7 but got {result}"
    print("[TEST PASS] subtract()")

def test_multiply():
    result = server.multiply(6, 7)
    assert result == 42, f"multiply(6, 7) expected 42 but got {result}"
    print("[TEST PASS] multiply()")

def test_divide_by_zero_guard():
    try:
        server.divide(1, 0)
        assert False, "divide(1, 0) should raise ValueError but did not!"
    except ValueError:
        print("[TEST PASS] divide_by_zero guard works")
    except ZeroDivisionError:
        assert False, "divide(1, 0) raised ZeroDivisionError instead of ValueError"

if __name__ == "__main__":
    test_add()
    test_subtract()
    test_multiply()
    test_divide_by_zero_guard()
    print("[ALL TESTS PASSED]")
"""
        ),
    ],
    test_commands=["python3 test_server.py"],
)


# ═══════════════════════════════════════════════════════════
#  FIXTURE 3 — FAILING: missing import dependency
# ═══════════════════════════════════════════════════════════
FAILING_IMPORT_SERVER = CoderOutput(
    project_name="missing-dep-mcp-server",
    language="python",
    runtime_version="3.11",
    entrypoint_file="server.py",
    env_vars={},
    files=[
        CodeFile(
            path="requirements.txt",
            content="# intentionally empty\n"
        ),

        CodeFile(
            path="server.py",
            content="""\
\"\"\"
MCP server that imports a non-existent internal module.
This simulates a Coder Agent generating code with a missing dependency.
\"\"\"
import mcp_nonexistent_lib_xyz   # will ALWAYS fail: ModuleNotFoundError

def compute(data: list) -> float:
    return mcp_nonexistent_lib_xyz.sum(data)

if __name__ == "__main__":
    print("[Broken MCP Server] This line is never reached")
"""
        ),

        CodeFile(
            path="test_server.py",
            content="""\
import importlib.util

spec = importlib.util.spec_from_file_location("server", "server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)   # ModuleNotFoundError fires here

def test_compute():
    result = server.compute([1, 2, 3, 4, 5])
    assert result == 15.0, f"Expected 15.0 but got {result}"
    print("[TEST PASS] compute()")

if __name__ == "__main__":
    test_compute()
    print("[ALL TESTS PASSED]")
"""
        ),
    ],
    test_commands=["python3 test_server.py"],
)
