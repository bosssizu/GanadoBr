# GanadoBravo v39i — robusto contra timeouts (retries + diag)

## Novedades
- Tiempo de espera del modelo **configurable** (`LLM_TIMEOUT_SEC`, default 15s).
- **Reintentos** con backoff (`LLM_RETRIES`, default 2).
- Endpoint **/api/diag** para verificar flags y último error.
- **WATCHDOG_SECONDS** elevado (default 30s) — ajústalo: debe ser > `LLM_TIMEOUT_SEC * (LLM_RETRIES+1) + 5`.
- Mantiene post-proceso que evita "Cebú puro" sin rasgos fuertes.

## Variables de entorno (Railway)
```
ENABLE_BREED=1
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
LLM_TIMEOUT_SEC=15
LLM_RETRIES=2
WATCHDOG_SECONDS=35
MAX_IMAGE_MB=8
# Opcional: OPENAI_BASE_URL (o usa Azure con LLM_PROVIDER=azure + claves)
```

## Probar
- GET `/api/health` → ok
- GET `/api/diag` → revisa que tus flags están activos
- POST `/evaluate` con una imagen
```bash
curl -F "file=@foto.jpg" -F "mode=levante" https://TU_APP/evaluate
```
