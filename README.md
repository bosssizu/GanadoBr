# GanadoBravo v39n — time‑budget + modos (levante / vaca_flaca / engorde)

## Cambios clave
- **Sin 502 por timeout**: llamadas al modelo con **presupuesto de tiempo** (`TIME_BUDGET_SEC`, default 9s). Si se excede o falla, cae a baseline **en ese mismo request**.
- **Time settings por defecto**: `LLM_TIMEOUT_SEC=7`, `LLM_RETRIES=0`, `WATCHDOG_SECONDS=20`.
- **Modos de decisión**:
  - **levante** (más permisivo que subasta).
  - **vaca_flaca**: tolera BCS bajo si el puntaje mínimo y riesgo son aceptables.
  - **engorde**: prefiere BCS 2.5–3.8; penaliza >4.6 o <1.8.

## Vars en Railway
```
ENABLE_AI_RUBRIC=1
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
LLM_TIMEOUT_SEC=7
LLM_RETRIES=0
TIME_BUDGET_SEC=9
WATCHDOG_SECONDS=20
ENABLE_BREED=1
MAX_IMAGE_MB=8
```
