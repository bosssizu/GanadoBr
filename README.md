# GanadoBravo v39b (full)

Endpoints:
- `GET /` -> UI simple
- `GET /api/health` -> ping
- `POST /evaluate` **y** `POST /api/eval` -> compatibilidad con ambas rutas

Env/deploy:
```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
# abre http://localhost:8000
```
