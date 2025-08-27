
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import os, traceback

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
        return HTMLResponse("<h1>GanadoBravo</h1><p>ASGI fallback.</p>")
    @fa.get("/healthz")
    def healthz():
        return {"ok": False, "asgi_fallback": True, "error": error_msg}
    return fa

try:
    from main_app import app as fastapi_app
    app = fastapi_app
except Exception:
    err = traceback.format_exc()
    app = _fallback_app(err)
