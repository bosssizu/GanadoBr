# GanadoBravo v39h — Clasificación de raza calibrada

- Prompt oculto pide **scores** (indicus/taurus) + **cues** (giba, orejas, dewlap, cuernos, pelaje) + `verdict`.
- Post-proceso evita "Cebú puro" si los rasgos fuertes **no** están presentes; devuelve **Cruza (… dominante)** cuando corresponde.
- Mantiene watchdog (10s) y límites anti-502.

## Env
```
ENABLE_BREED=1
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
# o Azure
LLM_PROVIDER=azure
AZURE_OPENAI_ENDPOINT=...
AZURE_OPENAI_DEPLOYMENT=...
AZURE_OPENAI_API_KEY=...
OPENAI_API_VERSION=2024-02-15-preview
```
