# GanadoBravo v39f — Watchdog + Logs (anti-502)

## Claves anti-502
- **WATCHDOG_SECONDS=8** (por defecto) → si el pipeline tarda más, responde 504 JSON (no deja que el proxy corte en 502).
- **ENABLE_BREED=1** es requerido para activar la llamada al modelo. Por defecto está **apagado** (evita timeouts).
- Límite de imagen **MAX_IMAGE_MB=8** (configurable).
- Endpoint `/api/diag` expone últimos errores y flags de entorno.

## Variables de entorno típicas (Railway)
- (Recomendado al inicio) **no usar el modelo**:
  ```
  ENABLE_BREED=0
  ```
- Si quieres usar **OpenAI** (activar explícitamente):
  ```
  ENABLE_BREED=1
  OPENAI_API_KEY=sk-...
  OPENAI_MODEL=gpt-4o-mini      # opcional
  OPENAI_BASE_URL=https://api.openai.com/v1   # opcional
  ```
- O **Azure OpenAI**:
  ```
  ENABLE_BREED=1
  LLM_PROVIDER=azure
  AZURE_OPENAI_ENDPOINT=https://TU-RECURSO.openai.azure.com
  AZURE_OPENAI_DEPLOYMENT=nombre-del-deployment
  AZURE_OPENAI_API_KEY=...
  OPENAI_API_VERSION=2024-02-15-preview
  ```
- Otros:
  ```
  WATCHDOG_SECONDS=8
  MAX_IMAGE_MB=8
  ```

## Endpoints
- `GET /api/health` → ok/version
- `GET /api/diag` → flags + último error
- `POST /evaluate` y `POST /api/eval` → `file`, `mode`

## Prueba rápida
1. Despliega con `bash start.sh` como start command.
2. Abre `/api/health` → debe responder.
3. Abre `/api/diag` → verifica `ENABLE_BREED` y demás.
4. Sube imagen en `/` o haz curl:
   ```bash
   curl -F "file=@foto.jpg" -F "mode=levante" https://TU_APP/evaluate
   ```
Si aparece 504 (watchdog), sube `WATCHDOG_SECONDS` o desactiva modelo (ENABLE_BREED=0).
