import os
import pytest
from playwright.sync_api import Page, expect
import threading
import time
import subprocess
import requests

# Helper to run streamlit in background for tests
@pytest.fixture(scope="session", autouse=True)
def run_streamlit():
    app_path = os.path.join(os.path.dirname(__file__), "app.py")
    process = subprocess.Popen(
        ["streamlit", "run", app_path, "--server.port", "8502", "--server.headless", "true"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait for the server to start
    for _ in range(30):
        try:
            response = requests.get("http://localhost:8502/_stcore/health")
            if response.status_code == 200:
                break
        except requests.ConnectionError:
            pass
        time.sleep(1)
        
    yield
    process.terminate()

def test_page_loads_and_has_correct_title(page: Page):
    page.goto("http://localhost:8502")
    expect(page).to_have_title("MCP-Forge Web Studio")
    expect(page.locator("h1")).to_contain_text("Web Studio Input Form")

def test_form_validation_empty_submission(page: Page):
    page.goto("http://localhost:8502")
    # Click the submit button without filling the required spec
    page.get_by_role("button", name="Generate & Verify MCP").click()
    
    # Check for the error message
    expect(page.locator(".stAlert")).to_contain_text("API Specification content is required")

def test_form_submission_with_mock_data(page: Page):
    page.goto("http://localhost:8502")
    
    # Fill out the required text area
    mock_spec = '{"swagger": "2.0", "info": {"title": "Test"}, "paths": {}}'
    page.locator("textarea[aria-label='Paste API Specification here']").fill(mock_spec)
    
    # Fill optional fields
    page.locator("input[aria-label='2. Service Name [OPTIONAL]']").fill("TestService")
    
    # Click submit
    page.get_by_role("button", name="Generate & Verify MCP").click()
    
    # We should see the spinner or success message depending on what the backend does.
    # We wait for either an error (if the backend fails due to dummy data) or success.
    # This just tests that the UI doesn't crash on submission.
    
    # Wait a bit for the processing
    page.wait_for_timeout(2000)
    
    # Check that it attempted the submission
    alert_locators = page.locator(".stAlert")
    # It might succeed or fail depending on how compile_to_mcp handles dummy data, but UI should handle both gracefully.
    expect(alert_locators.first).to_be_visible()
