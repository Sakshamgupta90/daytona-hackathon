import os
from dotenv import load_dotenv
from daytona import Daytona, DaytonaConfig

# Load environment variables from .env file if present
load_dotenv()

# Get Daytona API Key and URL from environment variables
api_key = os.getenv("DAYTONA_API_KEY", "your-api-key")
api_url = os.getenv("DAYTONA_API_URL") # optional self-hosted URL

print(f"Initializing Daytona with API Key: {api_key[:6]}..." if api_key != "your-api-key" else "Warning: Using default placeholder 'your-api-key'")
if api_url:
    print(f"Using custom Daytona API URL: {api_url}")

# Define the configuration
if api_url:
    config = DaytonaConfig(api_key=api_key, api_url=api_url)
else:
    config = DaytonaConfig(api_key=api_key)

# Initialize the Daytona client
daytona = Daytona(config)

print("Spawning/creating a new Daytona sandbox...")
try:
    # Create the Sandbox instance
    sandbox = daytona.create()
    print(f"Sandbox created successfully! Sandbox ID: {sandbox.id}")

    # Run the code securely inside the Sandbox
    code_to_run = 'print("Hello World from code!")'
    print(f"Executing code inside sandbox: {code_to_run}")
    response = sandbox.process.code_run(code_to_run)

    if response.exit_code != 0:
        print(f"Error executing code (Exit Code {response.exit_code}): {response.result}")
    else:
        print("Success! Execution output:")
        print(response.result)

except Exception as e:
    print(f"An error occurred during sandbox creation/execution: {e}")
