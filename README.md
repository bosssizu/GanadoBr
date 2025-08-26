# GanadoBravo v39d (robusto contra 502)

## Claves para evitar 502
- **Timeouts cortos** en llamadas a OpenAI/Azure (10s) con *fallback* inmediato.
- **Si no configuras API key**, la raza hace *fallback al instante* (sin red).
- **Deshabilitar raza temporalmente**: `BREED_DISABLED=1` (garantiza latencia mínima).
- **Límite de imagen**: 8 MB (responde 413 si se excede).

## Env
OpenAI:
- `OPENAI_API_KEY` (opcional)
- `OPENAI_MODEL` (default `gpt-4o-mini`)
- `OPENAI_BASE_URL` (opcional)

Azure OpenAI:
- `LLM_PROVIDER=azure`
- `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_API_KEY`
- `OPENAI_API_VERSION=2024-02-15-preview`

Control:
- `BREED_DISABLED=1` → desactiva llamada al modelo (usa fallback local).

## Run local
```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

## Endpoints
- `GET /api/health` → {"ok":true,"version":"v39d"}
- `POST /evaluate` o `/api/eval` → form-data: `file`, `mode`
