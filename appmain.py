

from fastapi import Response
from starlette.requests import Request

@app.get("/healthz")
def healthz():
    return {"ok": True, "version": APP_VERSION}

# Friendly 405 for GET /evaluate
@app.get("/evaluate")
def evaluate_get_hint():
    return JSONResponse({"status":"error","message":"Use POST /evaluate con archivo 'file' y campo 'mode'."}, status_code=405)

# Catch‑all fallback: sirve index para rutas que no sean /api* ni /static*
@app.get("/{path:path}", response_class=HTMLResponse)
def catch_all(path: str):
    if path.startswith("api") or path.startswith("static"):
        return JSONResponse({"detail":"Not Found"}, status_code=404)
    return FileResponse(os.path.join(static_dir, "index.html"))


@app.get("/routes")
def routes():
    return [{"path": r.path, "name": getattr(r.app, "__name__", None)} for r in app.router.routes]
