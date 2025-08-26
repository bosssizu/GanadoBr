# GanadoBravo v39g — triple-quoted prompt (fix SyntaxError)

- Prompt oculto en **triple comilla** para evitar `SyntaxError: unterminated string literal`.
- **Breed OFF por defecto**: requiere `ENABLE_BREED=1` para activar el llamado al modelo.
- Watchdog de 8s (ajustable con `WATCHDOG_SECONDS`).

## Env (Railway)
```
ENABLE_BREED=0            # recomendado al inicio
WATCHDOG_SECONDS=8
MAX_IMAGE_MB=8
# Para activar modelo:
# ENABLE_BREED=1
# OPENAI_API_KEY=sk-...
# OPENAI_MODEL=gpt-4o-mini
# (o Azure: LLM_PROVIDER=azure + variables de Azure)
```

## Run local
```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
