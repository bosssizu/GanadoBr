# GanadoBravo v39j — Condition Gated

## Qué hace
- **Prompt oculto de condición corporal (BCS)** que devuelve BCS (1–5) + señales (dorsal, posterior, pecho) + `risk_hint`.
- **Gating**: si BCS < 2.6, baja automáticamente **línea dorsal**, **grupo posterior**, **pecho/ancho** y **sube el riesgo**; además **elimina el bono posterior** si BCS < 3.4.
- **Decisión** limitada por BCS: si BCS < 2.4 → como máximo *Considerar (bajo)*; si BCS < 2.0 o riesgo ≥ 0.6 → *No comprar*.
- **Fallback heurístico** (Pillow + edges) cuando el modelo no está disponible.

## Variables
- `ENABLE_CONDITION=1` (default) — activa el prompt de condición.
- `ENABLE_BREED=1` (opcional) — activa el prompt de raza (si tienes API key).
- `OPENAI_API_KEY` + `OPENAI_MODEL` (o Azure con `LLM_PROVIDER=azure` y sus claves).
- Timeouts/retries heredados de versiones previas: `LLM_TIMEOUT_SEC`, `LLM_RETRIES`, `WATCHDOG_SECONDS`.

## Notas
- Mantiene **todas las métricas morfológicas** visibles.
- **Salud** sigue mostrando cada ítem y “No se detectaron problemas…” cuando corresponde.
