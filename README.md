# GanadoBravo v39k-fullui — Fix UI

- Restaura la **UI completa** (cards, rúbrica, salud, raza).
- Mantiene backend de **v39k** (stronger gating por BCS).
- Deja una página de **debug** en `/static/debug.html` (JSON crudo).

## Deploy rápido
- Start: `bash start.sh`
- Env sugerido:
```
WATCHDOG_SECONDS=30
MAX_IMAGE_MB=8
# Opcional para raza:
ENABLE_BREED=0
```
