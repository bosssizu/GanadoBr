# GanadoBravo — Diagnóstico v30

## Archivos
- `static/index.html` → UI limpia y validada (mismo origen por defecto). Si tu API está en otro dominio, edita `<meta name="api-base">`.
- `static/tester-evaluate.html` → Formulario **sin JS** que llama `POST /evaluate` directo.
  
## Pasos rápidos
1. Abre `/static/tester-evaluate.html`:
   - Sube una imagen y envía. **Debe** devolver JSON o un cuerpo con el resultado. Si falla:
     - Abre `/docs` y confirma que exista **POST /evaluate**.
     - Copia el **status** y el texto del error.
2. Abre `/static/index.html`:
   - Sube imagen → “Vista previa” debe aparecer.
   - Clic **Evaluar** → Si falla, verás un recuadro rojo con el error (timeout/404/500).

## Notas
- Este build no toca tu backend. Sólo añadimos un tester HTML para aislar problemas.
- Si el tester funciona pero el `index.html` no, la causa es de JS o de `api-base` distinto.
- Si el tester también falla, tu endpoint `/evaluate` no está respondiendo como el frontend espera.
