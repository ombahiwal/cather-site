# Catheter Site Triage (demo)

## Run locally (single command)
From the repository root:

```bash
chmod +x start_web.sh   # once
./start_web.sh          # installs deps, then launches gunicorn on 0.0.0.0:${PORT:-5000}
```

Ensure `GEMINI_API_KEY` is set in your shell before running (or export it inline when invoking the script). The script reuses `.venv` by default and writes uploads/history to `backend/storage` unless `STORAGE_DIR` is overridden.

## Run locally (manual steps)
1. `python -m venv venv`
2. `source venv/bin/activate` (or `venv\Scripts\activate` on Windows)
3. `pip install -r backend/requirements.txt`
4. `cd backend`
5. `export FLASK_APP=app.py`
6. `export GEMINI_API_KEY=your_key_here`
7. `flask run --host=0.0.0.0 --port=5000`

The SPA is served from `frontend/`, so opening http://127.0.0.1:5000 loads the UI.

## Deploy to Render
This repo includes `render.yaml`, so you can click **New > Blueprint** in Render and point it at this GitHub repository.

Key settings:
- The blueprint provisions a Python web service named `catheter-triage` that installs `backend/requirements.txt` and runs `gunicorn app:app --chdir backend --bind 0.0.0.0:$PORT`.
- Define the required environment variables in the Render dashboard:
	- `GEMINI_API_KEY` (mark as secret)
	- Optional `GEMINI_MODEL` override (defaults to `models/gemini-2.5-pro`).
- A persistent disk (`history-store`) is mounted at `/data` and ultimately used via `STORAGE_DIR=/data/storage` to retain uploaded images and the history JSON between deploys.

After the deploy succeeds, Render exposes a public HTTPS URL where the same UI/API are available.
