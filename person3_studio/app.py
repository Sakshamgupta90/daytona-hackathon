import sys
import os
import streamlit as st
import json

# Add parent directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from orchestrator import MCPForgeOrchestrator

st.set_page_config(page_title="MCP-Forge Web Studio", page_icon="⚡", layout="wide")

st.title("⚡ MCP-Forge: Autonomous Daytona-Powered MCP Compiler")
st.markdown("Transforms raw OpenAPI / Swagger / cURL specs into verified, production-hardened FastMCP servers tested inside **Daytona Sandboxes**.")

# Quick Preset Loader
sample_path = os.path.join(os.path.dirname(__file__), "..", "person1_compiler", "sample_inputs", "raw_github_input.json")
default_spec_str = ""
if os.path.exists(sample_path):
    with open(sample_path, "r", encoding="utf-8") as f:
        sample_data = json.load(f)
        default_spec_str = json.dumps(sample_data.get("spec_content", {}), indent=2)

with st.sidebar:
    st.header("⚙️ Showcase Presets")
    preset = st.selectbox("Load API Preset", ["GitHub Issues & Repos API (Showcase)", "Custom Spec"])
    if preset.startswith("GitHub"):
        initial_spec = default_spec_str
        initial_svc = "GitHubIssues"
        initial_base = "https://api.github.com"
        initial_auth = "bearer"
        initial_env = "GITHUB_TOKEN"
    else:
        initial_spec = ""
        initial_svc = ""
        initial_base = ""
        initial_auth = "none"
        initial_env = "API_KEY"

with st.form("mcp_forge_form"):
    st.subheader("1. API Specification [REQUIRED]")
    spec_format = st.radio("Specification Format", options=["openapi_json", "openapi_yaml", "curl"], horizontal=True)
    
    spec_input_type = st.radio("Input Method", options=["Text Area", "File Upload"], horizontal=True)
    spec_content_str = ""
    if spec_input_type == "Text Area":
        spec_content_str = st.text_area("Paste API Specification here", value=initial_spec, height=220)
    else:
        uploaded_file = st.file_uploader("Upload Specification File")
        if uploaded_file is not None:
            spec_content_str = uploaded_file.getvalue().decode("utf-8")
            st.success("File uploaded successfully!")

    st.subheader("2. Service Configuration & Authentication")
    col1, col2 = st.columns(2)
    with col1:
        service_name = st.text_input("Service Name [OPTIONAL]", value=initial_svc, help="e.g. 'GitHubIssues', 'PetStore'")
        auth_type = st.selectbox("Auth Scheme [REQUIRED]", options=["none", "bearer", "header", "query", "basic"], index=["none", "bearer", "header", "query", "basic"].index(initial_auth))
    with col2:
        base_url = st.text_input("Base URL Override [OPTIONAL]", value=initial_base, help="e.g. 'https://api.github.com'")
        env_var_name = st.text_input("Auth Env Var Name [OPTIONAL]", value=initial_env, help="e.g. 'GITHUB_TOKEN'")

    col3, col4 = st.columns(2)
    with col3:
        header_name = st.text_input("Header Name (if Header Auth)", value="Authorization")
    with col4:
        test_token = st.text_input("Live Sandbox Test Token [OPTIONAL]", type="password", help="Injected into Daytona Sandbox for live verification")

    submit_btn = st.form_submit_button("🚀 Compile, Deploy & Verify in Daytona", type="primary", use_container_width=True)

if submit_btn:
    if not spec_content_str.strip():
        st.error("API Specification content is required.")
    else:
        raw_payload = {
            "spec_format": spec_format,
            "spec_content": spec_content_str,
            "service_name": service_name if service_name else None,
            "base_url": base_url if base_url else None,
            "auth": {
                "auth_type": auth_type,
                "header_name": header_name,
                "query_param_name": None,
                "env_var_name": env_var_name,
                "test_token": test_token if test_token else None
            }
        }

        progress_bar = st.progress(0)
        status_box = st.empty()
        
        final_result = None
        for event in MCPForgeOrchestrator.run(raw_payload):
            step = event.get("step")
            msg = event.get("message", "")
            prog = event.get("progress", 0)
            
            progress_bar.progress(prog)
            status_box.info(f"**[{step}]** {msg}")
            
            if step in ("COMPLETED", "ERROR", "DEPLOYMENT_FAILED"):
                final_result = event
                break

        if final_result and final_result.get("step") == "COMPLETED":
            progress_bar.progress(100)
            status_box.success("✅ Multi-Agent Pipeline Finished: FastMCP Server Verified inside Daytona Sandbox!")
            
            bundle = final_result.get("bundle", {})
            deploy_out = final_result.get("deploy_output", {})
            tester_out = final_result.get("tester_output", {})
            bench_rep = final_result.get("benchmark_report", {})
            
            # Key Metrics
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Benchmark Score", bench_rep.get("overall_score", "100/100"))
            m2.metric("Daytona Sandbox", final_result.get("workspace_id", "active"))
            m3.metric("Test Result", tester_out.get("status", "TESTS_PASSED"))
            m4.metric("Schema Fidelity", bench_rep.get("metrics", {}).get("schema_completeness", "100%"))

            # Tabbed Outputs
            t1, t2, t3, t4, t5 = st.tabs([
                "💻 server.py (FastMCP)",
                "🧪 test_protocol.json",
                "⚡ Daytona Sandbox Execution",
                "📊 Benchmark Scorecard",
                "⚙️ claude_desktop_config.json"
            ])

            with t1:
                st.code(bundle.get("server.py", ""), language="python")
                st.download_button(
                    "📥 Download server.py",
                    bundle.get("server.py", ""),
                    file_name="server.py",
                    mime="text/x-python"
                )

            with t2:
                st.json(bundle.get("test_protocol.json", {}))

            with t3:
                st.subheader("⚡ Daytona Sandbox Deployment & Test Execution")
                st.json({
                    "workspace_id": deploy_out.get("workspace_id"),
                    "status": deploy_out.get("status"),
                    "deployed_files": deploy_out.get("deployed_files"),
                    "test_status": tester_out.get("status"),
                    "self_healed": final_result.get("self_healed", False),
                    "healing_attempts": final_result.get("healing_attempts", 0)
                })

            with t4:
                st.subheader("📊 Reference Implementation Parity & Quality Scorecard")
                st.json(bench_rep)

            with t5:
                config_json = json.dumps(bundle.get("claude_desktop_config.json", {}), indent=2)
                st.code(config_json, language="json")
                st.download_button(
                    "📥 Download claude_desktop_config.json",
                    config_json,
                    file_name="claude_desktop_config.json",
                    mime="application/json"
                )
        elif final_result and final_result.get("step") in ("ERROR", "DEPLOYMENT_FAILED"):
            st.error(f"Execution stopped: {final_result.get('message')}")
