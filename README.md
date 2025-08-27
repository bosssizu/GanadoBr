# GanadoBravo v39l-fullui — AI end-to-end (UI completa)

- La **rúbrica completa**, **BCS** y **riesgo** vienen del **modelo** (OpenAI o Azure) con timeouts y reintentos.
- Si el modelo falla, cae al **baseline**.
- UI completa (cards). Diagnóstico en `/api/diag`.

## Variables (Railway)
```
ENABLE_AI_RUBRIC=1
LLM_PROVIDER=openai            # o azure
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
LLM_TIMEOUT_SEC=18
LLM_RETRIES=2
WATCHDOG_SECONDS=40            # >= timeout*(retries+1)+5
ENABLE_BREED=0|1               # opcional
MAX_IMAGE_MB=8
```
