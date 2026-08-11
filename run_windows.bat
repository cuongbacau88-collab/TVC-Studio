@echo off
if not exist .venv (
  python -m venv .venv
)
call .venv\Scripts\activate
pip install -r requirements.txt
set ADMIN_PASSWORD=ChangeMe123!
set WORKER_TOKEN=change-worker-token
uvicorn app:app --host 0.0.0.0 --port 8000
