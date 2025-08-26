# GanadoBravo v39e — prompt corregido (Railway-safe)

Cambios:
- Arreglado `SyntaxError` por string sin cerrar en el prompt oculto.
- Mantiene timeouts cortos y *fallback* seguro para evitar 502.
- Razones de salud corregidas cuando todo está descartado.

Env claves:
- `BREED_DISABLED=1` para desactivar la llamada al modelo (pruebas sin red).
- `OPENAI_API_KEY` (o Azure: `LLM_PROVIDER=azure` + variables correspondientes).
- `OPENAI_MODEL` opcional (`gpt-4o-mini` por defecto).

Run local:
```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
