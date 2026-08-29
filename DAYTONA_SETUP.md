# 🔑 Daytona Sandbox API Setup Guide

This guide explains how to get your Daytona API key and configure the environment for the **MCP Forge Deployer & Tester Agents**.

---

## 🛠️ Step 1: Generate a Daytona API Key

### Option A: Using the Daytona Web Dashboard (Recommended)
1. Go to [https://app.daytona.io](https://app.daytona.io) and log in.
2. Navigate to **Settings** $\rightarrow$ **API Keys** (or Profile $\rightarrow$ Access Tokens).
3. Click **Generate New API Key**.
4. Give it a name (e.g. `mcp-forge-hackathon`).
5. Copy the generated API key string immediately (you will not be able to view it again).

### Option B: Using the Daytona CLI
If you have the Daytona CLI installed on your machine:
```bash
# Log in to Daytona
daytona server login

# Generate an API key
daytona api-key generate
```

---

## ⚙️ Step 2: Configure Environment Variables

1. Copy `.env.example` to create your local `.env` file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and fill in your details:
   ```env
   DAYTONA_API_KEY=daytona_api_key_xxxxxxxxxxxx
   DAYTONA_SERVER_URL=https://app.daytona.io/api
   DAYTONA_TARGET=us

   # Toggle MOCK_SANDBOX=true to test locally for free (no API credits used)
   # Toggle MOCK_SANDBOX=false to run on real Daytona Cloud Sandboxes
   MOCK_SANDBOX=true
   ```

---

## 💡 Step 3: Fast Offline Testing (Mock Mode)

During development and hackathon iteration:
- Keep `MOCK_SANDBOX=true` in your `.env`.
- The Deployer & Tester agents will simulate the Daytona sandbox API locally on disk with zero network delay and zero Daytona compute cost.
- Flip `MOCK_SANDBOX=false` when ready to run live Cloud Sandboxes for your final demo!
