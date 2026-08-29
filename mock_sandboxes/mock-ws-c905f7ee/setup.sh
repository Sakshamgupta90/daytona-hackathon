#!/usr/bin/env bash
set -e
echo '=== [Daytona Sandbox] Installing Dependencies ==='
if [ -f requirements.txt ]; then
    pip install -r requirements.txt --quiet --disable-pip-version-check || true
fi
echo '=== [Daytona Sandbox] Environment Ready ==='
