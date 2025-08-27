
# GanadoBravo — Fullstack (v1)

Stack mínimo **FastAPI + Frontend**.

## Endpoints
- `GET /` -> UI
- `POST /evaluate` y `POST /api/evaluate` (alias) -> body: `file` (imagen), `mode` (`levante`,`vaca_flaca`,`engorde`)
- `GET /healthz` y `GET /api/diag`

## Run
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
# abre http://localhost:8000
```

## IA
La UI muestra **IA activa** si `ENABLE_AI=1` o `OPENAI_API_KEY` está definido.
El scoring es determinista local; puedes reemplazar `_evaluate_bytes` por tu pipeline real.
