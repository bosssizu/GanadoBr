# GanadoBravo v39p — QC hidden en cualquier UI + preview irrompible

- Misma lógica backend que **v39n** (time‑budget + modos: levante, vaca_flaca, engorde).
- **Oculta 'Calidad de entrada'** incluso si tu UI vieja la inyecta (CSS + MutationObserver).
- **Vista previa blindada**: DataURL + retry onerror + re‑aplica al volver de background.

Variables sugeridas:
```
LLM_TIMEOUT_SEC=7
LLM_RETRIES=0
TIME_BUDGET_SEC=9
WATCHDOG_SECONDS=20
ENABLE_AI_RUBRIC=1
```
