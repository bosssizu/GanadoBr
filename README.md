# GanadoBravo v39 — Full functional

- FastAPI backend with real pipeline (`pipeline_real.py`) — no external AI calls.
- UI renders **all morphological metrics** and **all health conditions** (each marked as *Descartado* or *Sospecha*).
- Endpoints:
  - `GET /` — SPA
  - `POST /evaluate` — form-data (`file`, `mode` = `levante`|`subasta`)
- Run locally:
  ```bash
  pip install fastapi uvicorn pillow
  uvicorn main:app --reload --port 8000
  ```
