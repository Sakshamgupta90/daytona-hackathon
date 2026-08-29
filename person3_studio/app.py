import sys
import os
import streamlit as st
import json

# Add parent directory to sys.path to import person1_compiler
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from person1_compiler.pipeline import compile_to_mcp

st.set_page_config(page_title="MCP-Forge Web Studio", layout="wide")

st.title("🖥️ Web Studio Input Form (Person 3 UI)")
st.markdown("Transforms raw OpenAPI / Swagger / cURL specs into verified FastMCP servers.")

with st.form("mcp_forge_form"):
    st.subheader("1. API Specification [REQUIRED]")
    spec_format = st.radio("Specification Format", options=["openapi_json", "openapi_yaml", "curl"])
    
    spec_input_type = st.radio("Input Method", options=["Text Area", "File Upload"])
    spec_content_str = ""
    if spec_input_type == "Text Area":
        spec_content_str = st.text_area("Paste API Specification here", height=200)
    else:
        uploaded_file = st.file_uploader("Upload Specification File")
        if uploaded_file is not None:
            spec_content_str = uploaded_file.getvalue().decode("utf-8")
            st.success("File uploaded successfully!")

    st.subheader("Optional Overrides")
    col1, col2 = st.columns(2)
    with col1:
        service_name = st.text_input("2. Service Name [OPTIONAL]", help="e.g. 'GitHub Issues', 'PetStore'")
    with col2:
        base_url = st.text_input("3. Base URL Override [OPTIONAL]", help="e.g. 'https://api.github.com'")

    st.subheader("Authentication")
    auth_type = st.selectbox("4. Auth Scheme [REQUIRED]", options=["none", "bearer", "header", "query"], index=1)
    
    col3, col4 = st.columns(2)
    with col3:
        header_name = st.text_input("Header Name", value="Authorization", help="Only used if auth_type is 'header'")
        env_var_name = st.text_input("5. Auth Env Var Name [OPTIONAL]", value="API_KEY", help="e.g. 'GITHUB_TOKEN'")
    with col4:
        test_token = st.text_input("6. Test Token / API Key [OPTIONAL]", type="password", help="For live testing inside Daytona Sandbox")

    submit_btn = st.form_submit_button("🚀 Generate & Verify MCP")

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
        
        with st.spinner("Compiling API Spec to MCP Bundle..."):
            try:
                result = compile_to_mcp(raw_payload)
                st.success(f"Successfully generated MCP bundle for '{result.get('metadata', {}).get('service_name', 'Unknown')}'!")
                
                st.subheader("Generated Bundle")
                st.json(result.get('metadata', {}))
                
                with st.expander("server.py"):
                    st.code(result.get("server.py", ""), language="python")
                    
                with st.expander("requirements.txt"):
                    st.code(result.get("requirements.txt", ""), language="text")
                    
            except Exception as e:
                st.error(f"Error compiling to MCP: {str(e)}")
