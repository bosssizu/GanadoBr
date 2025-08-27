# GanadoBravo v39l-fullui-kpis — Riesgo y Bono visibles

- Mismo backend AI end-to-end (v39l).
- UI con **4 KPIs**: BCS, Puntaje global, **Riesgo** y **Bono posterior** (visibles).
- Vista previa **persistente** tras evaluar.
- Bloque de calidad de entrada oculto.

Variables sugeridas (Railway):
```
ENABLE_AI_RUBRIC=1
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
LLM_TIMEOUT_SEC=18
LLM_RETRIES=2
WATCHDOG_SECONDS=40
ENABLE_BREED=1        # opcional
MAX_IMAGE_MB=8
```
