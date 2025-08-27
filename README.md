# GanadoBravo v39r — UI pulida + Raza 100% AI

- **Decisión más grande** y coloreada por nivel.
- **Puntajes coloreados** (rojo→verde) tanto el global como cada métrica.
- **Raza** ahora es 100% AI con prompt oculto (OpenAI/Azure); fallback a "Cruza indicus×taurus" si falla.
- Backend con time‑budget y modos (levante, vaca_flaca, engorde).

Variables recomendadas:
```
ENABLE_AI_RUBRIC=1
ENABLE_BREED=1
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
BREED_MODEL=gpt-4o-mini
LLM_TIMEOUT_SEC=7
BREED_TIMEOUT_SEC=6
LLM_RETRIES=0
TIME_BUDGET_SEC=9
WATCHDOG_SECONDS=20
```
