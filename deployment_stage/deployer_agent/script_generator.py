import os
from typing import List
from .schemas import CodeFile, CoderOutput


class SetupScriptGenerator:
    """Auto-generates setup, dependency manifests, and runner bash scripts for Daytona sandbox."""

    @staticmethod
    def process_coder_output(coder_output: CoderOutput) -> List[CodeFile]:
        """
        Takes raw CoderOutput files and ensures required setup files (requirements.txt, setup.sh, run.sh)
        are automatically injected if missing.
        """
        existing_paths = {f.path for f in coder_output.files}
        generated_files = list(coder_output.files)

        if coder_output.language.lower() == "python":
            # 1. Ensure requirements.txt exists
            if "requirements.txt" not in existing_paths:
                generated_files.append(
                    CodeFile(
                        path="requirements.txt",
                        content="mcp>=1.0.0\nhttpx>=0.27.0\npytest>=8.0.0\npytest-json-report>=1.5.0\n"
                    )
                )

            # 2. Ensure setup.sh exists
            if "setup.sh" not in existing_paths:
                setup_content = (
                    "#!/usr/bin/env bash\n"
                    "set -e\n"
                    "echo '=== [Daytona Sandbox] Installing Dependencies ==='\n"
                    "if [ -f requirements.txt ]; then\n"
                    "    pip install -r requirements.txt --quiet --disable-pip-version-check || true\n"
                    "fi\n"
                    "echo '=== [Daytona Sandbox] Environment Ready ==='\n"
                )
                generated_files.append(CodeFile(path="setup.sh", content=setup_content))

            # 3. Ensure default test_commands exist if empty
            if not coder_output.test_commands:
                coder_output.test_commands = [
                    "bash setup.sh",
                    "python3 -m pytest -v --tb=short"
                ]

        elif coder_output.language.lower() in ("typescript", "javascript", "node"):
            # 1. Ensure package.json exists
            if "package.json" not in existing_paths:
                package_json = (
                    '{\n'
                    '  "name": "' + coder_output.project_name + '",\n'
                    '  "version": "1.0.0",\n'
                    '  "type": "module",\n'
                    '  "scripts": {\n'
                    '    "start": "node ' + coder_output.entrypoint_file + '",\n'
                    '    "test": "node --test"\n'
                    '  },\n'
                    '  "dependencies": {\n'
                    '    "@modelcontextprotocol/sdk": "^1.0.0"\n'
                    '  }\n'
                    '}\n'
                )
                generated_files.append(CodeFile(path="package.json", content=package_json))

            # 2. Ensure setup.sh exists
            if "setup.sh" not in existing_paths:
                setup_content = (
                    "#!/usr/bin/env bash\n"
                    "set -e\n"
                    "echo '=== [Daytona Sandbox] Installing Node Dependencies ==='\n"
                    "npm install\n"
                    "echo '=== [Daytona Sandbox] Environment Ready ==='\n"
                )
                generated_files.append(CodeFile(path="setup.sh", content=setup_content))

            # 3. Default test commands
            if not coder_output.test_commands:
                coder_output.test_commands = [
                    "bash setup.sh",
                    "npm test"
                ]

        return generated_files
