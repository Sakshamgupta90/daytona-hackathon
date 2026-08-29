import os
import logging
from typing import Optional
from .schemas import CoderOutput, DeployerOutput
from .script_generator import SetupScriptGenerator
from .sandbox_manager import BaseSandboxManager, get_sandbox_manager

logger = logging.getLogger("DeployerAgent")


class DeployerAgent:
    """
    Agent 3: Deployer Agent
    Accepts CoderOutput, generates setup scripts, provisions Daytona Sandbox,
    uploads files directly, installs dependencies, and passes active workspace payload to Tester Agent.
    """

    def __init__(self, sandbox_manager: Optional[BaseSandboxManager] = None):
        self.sandbox_manager = sandbox_manager or get_sandbox_manager()

    def deploy(self, coder_output: CoderOutput) -> DeployerOutput:
        """
        Orchestrates full deployment lifecycle into Daytona Sandbox.
        """
        logger.info(f"Starting Deployment for Project: {coder_output.project_name}")

        try:
            # 1. Process files & auto-generate missing setup scripts
            processed_files = SetupScriptGenerator.process_coder_output(coder_output)

            # 2. Provision Daytona / Mock Sandbox workspace
            workspace_id = self.sandbox_manager.create_workspace(
                project_name=coder_output.project_name,
                language=coder_output.language,
                env_vars=coder_output.env_vars
            )
            logger.info(f"Provisioned Sandbox Workspace ID: {workspace_id}")

            # 3. Direct File Upload (Only Coder + Setup files)
            uploaded_paths = []
            for file_obj in processed_files:
                self.sandbox_manager.upload_file(
                    workspace_id=workspace_id,
                    file_path=file_obj.path,
                    content=file_obj.content
                )
                uploaded_paths.append(file_obj.path)

            logger.info(f"Uploaded {len(uploaded_paths)} files directly to Sandbox.")

            # 4. Execute setup script (e.g. bash setup.sh or pip install on Windows)
            setup_res = self.sandbox_manager.exec_command(workspace_id, "bash setup.sh")
            if setup_res["exit_code"] != 0 and os.name == "nt":
                # Fallback on Windows without WSL
                setup_res = self.sandbox_manager.exec_command(workspace_id, "pip install -r requirements.txt --quiet")

            if setup_res["exit_code"] != 0:
                logger.error(f"Setup Script Failed inside Sandbox:\n{setup_res['stderr']}")
                # Cleanup the sandbox immediately to avoid resource leaks
                self.sandbox_manager.destroy_workspace(workspace_id)
                return DeployerOutput(
                    workspace_id=workspace_id,
                    status="DEPLOYMENT_FAILED",
                    project_name=coder_output.project_name,
                    language=coder_output.language,
                    entrypoint_file=coder_output.entrypoint_file,
                    deployed_files=uploaded_paths,
                    env_vars=coder_output.env_vars,
                    test_commands=coder_output.test_commands,
                    test_protocol=coder_output.test_protocol,
                    error_message=f"Setup failed (exit code {setup_res['exit_code']}): {setup_res['stderr']}",
                    raw_workspace_handle=None  # Cleaned up, no handle needed
                )

            # 5. Deployment Success -> Package Handoff Payload for Tester Agent
            return DeployerOutput(
                workspace_id=workspace_id,
                status="DEPLOYED",
                project_name=coder_output.project_name,
                language=coder_output.language,
                entrypoint_file=coder_output.entrypoint_file,
                deployed_files=uploaded_paths,
                env_vars=coder_output.env_vars,
                test_commands=coder_output.test_commands,
                test_protocol=coder_output.test_protocol,
                error_message=None,
                raw_workspace_handle=self.sandbox_manager
            )

        except Exception as e:
            logger.exception(f"Unexpected Deployment Error: {str(e)}")
            return DeployerOutput(
                workspace_id="NONE",
                status="DEPLOYMENT_FAILED",
                project_name=coder_output.project_name,
                language=coder_output.language,
                entrypoint_file=coder_output.entrypoint_file,
                deployed_files=[],
                env_vars=coder_output.env_vars,
                test_commands=coder_output.test_commands,
                test_protocol=coder_output.test_protocol,
                error_message=f"Exception during deployment: {str(e)}",
                raw_workspace_handle=None
            )
