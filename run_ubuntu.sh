#!/usr/bin/env bash
set -e
if [ ! -d .venv ]; then python3 -m venv .venv; fi
source .venv/bin/activate
pip install -r requirements.txt
export ADMIN_PASSWORD="${ADMIN_PASSWORD:-ChangeMe123!}"
export WORKER_TOKEN="${WORKER_TOKEN:-change-worker-token}"
uvicorn app:app --host 0.0.0.0 --port 8000
