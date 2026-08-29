import os
import shutil
import subprocess
import uuid
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional

logger = logging.getLogger("SandboxManager")


class BaseSandboxManager(ABC):
    """Abstract interface defining standard sandbox operations for Daytona and Mock drivers."""

    @abstractmethod
    def create_workspace(self, project_name: str, language: str, env_vars: Dict[str, str]) -> str:
        """Provisions a new sandbox workspace and returns workspace_id."""
        pass

    @abstractmethod
    def upload_file(self, workspace_id: str, file_path: str, content: str) -> bool:
        """Writes a single file directly to the sandbox workspace filesystem."""
        pass

    @abstractmethod
    def exec_command(self, workspace_id: str, command: str) -> Dict[str, Any]:
        """Executes a command inside the sandbox workspace and returns stdout, stderr, exit_code."""
        pass

    @abstractmethod
    def destroy_workspace(self, workspace_id: str) -> bool:
        """Deletes/tears down the sandbox workspace to free up memory and API quotas."""
        pass


class LocalMockSandboxManager(BaseSandboxManager):
    """
    Simulates Daytona Sandbox locally in an isolated temporary directory.
    Zero network latency, zero cost, 100% free testing during hackathon dev iteration!
    """

    def __init__(self, base_dir: str = "./mock_sandboxes"):
        self.base_dir = os.path.abspath(base_dir)
        os.makedirs(self.base_dir, exist_ok=True)
        self.active_workspaces: Dict[str, Dict[str, Any]] = {}

    def create_workspace(self, project_name: str, language: str, env_vars: Dict[str, str]) -> str:
        workspace_id = f"mock-ws-{uuid.uuid4().hex[:8]}"
        workspace_path = os.path.join(self.base_dir, workspace_id)
        os.makedirs(workspace_path, exist_ok=True)

        self.active_workspaces[workspace_id] = {
            "project_name": project_name,
            "language": language,
            "path": workspace_path,
            "env_vars": env_vars,
        }
        logger.info(f"[MockSandbox] Created workspace: {workspace_id} at {workspace_path}")
        return workspace_id

    def upload_file(self, workspace_id: str, file_path: str, content: str) -> bool:
        if workspace_id not in self.active_workspaces:
            raise ValueError(f"Workspace {workspace_id} not found.")

        workspace_path = self.active_workspaces[workspace_id]["path"]
        full_file_path = os.path.join(workspace_path, file_path)

        os.makedirs(os.path.dirname(full_file_path) if os.path.dirname(full_file_path) else workspace_path, exist_ok=True)
        with open(full_file_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"[MockSandbox] Uploaded file: {file_path}")
        return True

    def exec_command(self, workspace_id: str, command: str) -> Dict[str, Any]:
        if workspace_id not in self.active_workspaces:
            raise ValueError(f"Workspace {workspace_id} not found.")

        ws_info = self.active_workspaces[workspace_id]
        workspace_path = ws_info["path"]

        env = os.environ.copy()
        env.update(ws_info.get("env_vars", {}))

        try:
            res = subprocess.run(
                command,
                shell=True,
                cwd=workspace_path,
                capture_output=True,
                text=True,
                env=env,
                timeout=120,
            )
            return {
                "exit_code": res.returncode,
                "stdout": res.stdout,
                "stderr": res.stderr,
            }
        except subprocess.TimeoutExpired:
            return {
                "exit_code": 124,
                "stdout": "",
                "stderr": "Command execution timed out after 120 seconds.",
            }

    def destroy_workspace(self, workspace_id: str) -> bool:
        if workspace_id in self.active_workspaces:
            workspace_path = self.active_workspaces[workspace_id]["path"]
            if os.path.exists(workspace_path):
                shutil.rmtree(workspace_path, ignore_errors=True)
            del self.active_workspaces[workspace_id]
            logger.info(f"[MockSandbox] Destroyed workspace: {workspace_id}")
            return True
        return False


class DaytonaCloudSandboxManager(BaseSandboxManager):
    """
    Connects directly to Daytona Cloud using the official daytona Python SDK.
    Follows the exact Daytona onboarding guide API pattern.
    """

    def __init__(self, api_key: str):
        from daytona import Daytona, DaytonaConfig

        config = DaytonaConfig(api_key=api_key)
        self.client = Daytona(config)
        self.active_sandboxes: Dict[str, Any] = {}
        logger.info(f"[DaytonaCloud] Initialized Daytona SDK client")

    def create_workspace(self, project_name: str, language: str, env_vars: Dict[str, str]) -> str:
        logger.info(f"[DaytonaCloud] Provisioning new sandbox: {project_name} ({language})")

        sandbox = self.client.create()
        workspace_id = sandbox.id
        self.active_sandboxes[workspace_id] = sandbox

        logger.info(f"[DaytonaCloud] ✅ Sandbox created: ID={workspace_id}")
        return workspace_id

    def upload_file(self, workspace_id: str, file_path: str, content: str) -> bool:
        if workspace_id not in self.active_sandboxes:
            raise ValueError(f"Sandbox {workspace_id} not found in active sessions.")

        sandbox = self.active_sandboxes[workspace_id]
        encoded = content.encode("utf-8")
        sandbox.fs.upload_file(encoded, file_path)

        logger.info(f"[DaytonaCloud] Uploaded file: {file_path}")
        return True

    def exec_command(self, workspace_id: str, command: str) -> Dict[str, Any]:
        if workspace_id not in self.active_sandboxes:
            raise ValueError(f"Sandbox {workspace_id} not found in active sessions.")

        sandbox = self.active_sandboxes[workspace_id]
        logger.info(f"[DaytonaCloud] Executing: {command}")

        response = sandbox.process.exec(command, timeout=120)

        exit_code = getattr(response, 'exit_code', 0)
        stdout    = getattr(response, 'result', str(response))
        stderr    = getattr(response, 'stderr', "")

        return {
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
        }

    def destroy_workspace(self, workspace_id: str) -> bool:
        if workspace_id in self.active_sandboxes:
            sandbox = self.active_sandboxes[workspace_id]
            self.client.delete(sandbox)
            del self.active_sandboxes[workspace_id]
            logger.info(f"[DaytonaCloud] 🧹 Deleted sandbox: {workspace_id}")
            return True
        return False


def get_sandbox_manager() -> BaseSandboxManager:
    """
    Factory: Returns LocalMockSandboxManager or DaytonaCloudSandboxManager
    based on MOCK_SANDBOX environment variable in your .env file.
    """
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    is_mock = os.getenv("MOCK_SANDBOX", "true").lower() in ("true", "1", "yes")

    if is_mock:
        logger.info("[SandboxFactory] Using LocalMockSandboxManager (MOCK_SANDBOX=true)")
        return LocalMockSandboxManager()
    else:
        api_key = os.getenv("DAYTONA_API_KEY", "")

        if not api_key or api_key == "your_daytona_api_key_here":
            raise ValueError(
                "\n\n❌ DAYTONA_API_KEY not set!\n"
                "Steps to fix:\n"
                "  1. Run: cp .env.example .env\n"
                "  2. Open .env and paste your Daytona API key\n"
                "  3. Set MOCK_SANDBOX=false\n"
                "  4. Get your key at: https://app.daytona.io → Settings → API Keys\n"
            )

        logger.info("[SandboxFactory] Using DaytonaCloudSandboxManager (LIVE CLOUD)")
        return DaytonaCloudSandboxManager(api_key=api_key)

