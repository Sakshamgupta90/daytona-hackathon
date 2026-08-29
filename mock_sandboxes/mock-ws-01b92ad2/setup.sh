#!/usr/bin/env bash
set -e
echo '=== [Daytona Sandbox] Installing Python Dependencies ==='
python3 -m pip install --upgrade pip
if [ -f requirements.txt ]; then
    pip install -r requirements.txt
fi
echo '=== [Daytona Sandbox] Environment Ready ==='
