# GanadoBravo v39c — OpenAI prompt oculto para raza

## Endpoints
- `GET /` UI simple
- `GET /api/health` ping
- `POST /evaluate` y `POST /api/eval` aceptan `file` (imagen) y `mode` (`levante` | `subasta`).

## Variables de entorno (elige proveedor)
### OpenAI (recomendado)
- `OPENAI_API_KEY` = tu API key
- `OPENAI_MODEL` (opcional, por defecto `gpt-4o-mini`)
- `OPENAI_BASE_URL` (opcional, para proxies compatibles)

### Azure OpenAI (opcional)
- `LLM_PROVIDER=azure`
- `AZURE_OPENAI_ENDPOINT` (p.ej. https://TU-RECURSO.openai.azure.com)
- `AZURE_OPENAI_DEPLOYMENT` (nombre del deployment del modelo con soporte visión)
- `AZURE_OPENAI_API_KEY`
- `OPENAI_API_VERSION=2024-02-15-preview` (o la versión que uses)

> Si no hay configuración válida, el sistema hace *fallback* seguro y devuelve una raza genérica.

## Ejecutar local
```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
# http://localhost:8000
```

## Notas
- Raza: se usa **prompt oculto** (system) que obliga salida en JSON y describe cues morfológicos a evaluar.
- Salud: las **razones** ahora dicen “No se detectaron problemas de salud.” cuando todo el catálogo está **descartado**.
- Métricas: la rúbrica siempre incluye **todas** las métricas morfológicas.
