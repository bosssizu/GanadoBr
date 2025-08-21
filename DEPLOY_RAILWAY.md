# Deploy en Railway

## Pasos
1. Conecta el repo a Railway.
2. Asegúrate que `static/index.html` existe en el repo (está en este paquete).
3. Usa este Start Command (o deja que Railway lea el Procfile):
   ```
   bash start.sh
   ```
   - El script usa el puerto `$PORT` que Railway inyecta, y hace bind a `0.0.0.0`.
4. Variables:
   - `PORT`: inyectado por Railway automáticamente.
5. Verificación:
   - `/health` debe devolver `{"ok": true}`
   - `/` debe servir el UI (index.html)

## Logs y 502
- Un 502 con `connection dial timeout` suele indicar que el proceso **no está escuchando** en el `$PORT` o se cae al iniciar.
- Revisa los logs en Railway. Este script imprime versión de Python y listado de archivos al arrancar para ayudarte a diagnosticar.