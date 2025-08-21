# GanadoBravo — v38 (Real pipeline listo)

Este paquete llama TU lógica real mediante `pipeline_real.py`. Si ese archivo no está implementado,
el backend cae a un **mock** para no romper la UI (puedes forzar mock con `GB_MOCK=1`).

## Puntos de integración (implementa en `pipeline_real.py`)
- `run_metrics_pass(img, mode, pass_id)` → primera/segunda pasada de métricas
- `aggregate_metrics(m1, m2)` → combina las dos pasadas
- `detect_health(img, metrics)` → lista de salud (solo `Enfermedad = Resultado`)
- `run_breed_prompt(img)` → raza (prompt oculto, resaltar criollo/entrecruzamiento)
- `format_output(metrics, health, breed, mode)` → objeto final para la UI

## Formato de salida esperado por la UI
```jsonc
{
  "mode": "levante",
  "global_conf": 0.93,
  "decision_level": "CONSIDERAR_ALTO",   // NO_COMPRAR | CONSIDERAR_BAJO | CONSIDERAR_ALTO | COMPRAR
  "decision_text": "Considerar alto",
  "global_score": 7.4,
  "bcs": 3.5,
  "risk": 0.20,
  "posterior_bonus": 0.10,
  "notes": "texto",
  "qc": { "visible_ratio": 0.86, "stability": "alta", "auction_mode": false },
  "rubric": [ { "name": "Conformación", "score": 7.8, "obs": "..." } ],
  "reasons": ["..."],
  "health": [ { "name": "Lesión cutánea", "severity": "descartado" } ],
  "breed": { "name": "Criollo", "confidence": 0.58, "explanation": "..." }
}
```

## Cómo desplegar
1. Sube y despliega (Procfile/start.sh listos).
2. Implementa `pipeline_real.py` (puedes copiar tu código real aquí).
3. (Opcional) `GB_MOCK=0` para forzar uso real; con funciones `NotImplementedError` se pasará al mock.
4. Verifica `/health` y luego `/`.
