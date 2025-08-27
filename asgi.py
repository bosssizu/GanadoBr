
# ASGI smart loader: tries appmain.app, then main.app; fallback includes basic pages.
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
import os, traceback

app = None
err = None

def _fallback_app(error_msg: str):
    fa = FastAPI(title="GanadoBravo (ASGI fallback)")
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if os.path.isdir(static_dir):
        fa.mount("/static", StaticFiles(directory=static_dir), name="static")
    @fa.get("/", response_class=HTMLResponse)
    def index():
        idx = os.path.join(static_dir, "index.html")
        if os.path.exists(idx):
            return HTMLResponse(open(idx, "r", encoding="utf-8").read())
        return HTMLResponse("<h1>GanadoBravo</h1><p>ASGI fallback. Falta app principal.</p>")
    @fa.get("/healthz")
    def healthz():
        return {"ok": False, "asgi_fallback": True, "error": error_msg}
    @fa.get("/__asgi_error__")
    def asgi_error():
        return {"error": error_msg}
    return fa

try:
    # Prefer appmain.app (to avoid clashes con módulos llamados 'main')
    from appmain import app as fastapi_app
    app = fastapi_app
except Exception as e1:
    err = "appmain import failed: " + "\n" + traceback.format_exc()
    try:
        from main import app as fastapi_app
        app = fastapi_app
    except Exception as e2:
        err = err + "\n---\nmain import failed: " + "\n" + traceback.format_exc()
        app = _fallback_app(err)
