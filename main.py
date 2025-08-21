from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Any, Dict, List
from PIL import Image
import io
import os, pathlib, numpy as np, json, hashlib

from heuristics import run_auction_heuristics, apply_heuristic_scoring
from pathology import run_pathology_heuristic
from breed import run_breed_heuristic
from breed_ai import run_breed_ai

# Base directory for locating static files regardless of CWD
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
INDEX_HTML = STATIC_DIR / "index.html"
app = FastAPI(title="GanadoBravo v9d")


class RootRedirectMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.url.path == "/":
            from starlette.responses import RedirectResponse
            return RedirectResponse("/static/index.html", status_code=307)
        return await call_next(request)

# Register middleware
app.add_middleware(RootRedirectMiddleware)


# CORS (permite UI en otro dominio)
try:
    from starlette.middleware.cors import CORSMiddleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
except Exception:
    pass

CACHE: Dict[str, Dict[str, Any]] = {}

def _cfg() -> Dict[str, Any]:
    p = pathlib.Path("config.json")
    if p.exists():
        try: return json.loads(p.read_text(encoding="utf-8"))
        except Exception: return {}
    return {}

def _estimate_visible_ratio(img: Image.Image) -> float:
    g = img.convert("L").resize((512, int(512 * img.height / max(1, img.width))))
    arr = np.asarray(g, dtype=np.float32) / 255.0
    row_mean = arr.mean(axis=1)
    amp = row_mean.max() - row_mean.min()
    if amp > 0.35: return 0.40
    if amp > 0.20: return 0.52
    return 0.75

def _validate_input(img: Image.Image):
    cfg = _cfg()
    health = run_pathology_heuristic(img, mode, vis_ratio)
    d["health"] = health["health"]
    _health_override(d, d["health"], cfg)
    # --- breed evaluation (heuristic + AI) ---
    try:
        heur_b = run_breed_heuristic(img, cfg)
    except Exception:
        heur_b = {}
    try:
        ai_b = run_breed_ai(img, cfg, heur_b)
    except Exception:
        ai_b = {}
    d["breed"] = heur_b
    d["breed_ai"] = ai_b
    d.pop("raw_image", None)
    CACHE[key] = dict(d)
    return JSONResponse(d)

@app.post("/evaluate_batch")

@app.post("/evaluate")
async def evaluate(file: UploadFile = File(...), mode: str = Form("levante")):
    """Alias de /evaluate_batch para 1 archivo.
    Espera el campo multipart llamado **file** (coincide con el frontend).
    Devuelve el mismo formato (lista).
    """
    try:
        resp = await evaluate_batch(files=[file], mode=mode)  # type: ignore
        return resp
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        return JSONResponse({"error":"evaluate_failed","detail":str(e),"trace":tb}, status_code=500)



async def evaluate_batch(files: List[UploadFile] = File(...), mode: str = Form("levante")):
    try:
        resp = await evaluate_batch(files=[file], mode=mode)
        return resp
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        return JSONResponse({"error":"evaluate_failed","detail":str(e),"trace":tb}, status_code=500)


@app.get("/", response_class=HTMLResponse)
async def root():
    try:
        return FileResponse("static/index.html")
    except Exception:
        return HTMLResponse("<h1>GanadoBravo</h1><p>Sube el frontend en <code>/static/index.html</code></p>", status_code=200)


@app.get("/health")
async def healthcheck():
    return {"ok": True}

@app.get("/", response_class=HTMLResponse)
async def root():
    if INDEX_HTML.exists():
        return FileResponse(str(INDEX_HTML))
    return HTMLResponse("<h1>GanadoBravo</h1><p>Sube el frontend en <code>/static/index.html</code></p>", status_code=200)

@app.get("/", response_class=HTMLResponse)
async def root():
    # Try multiple candidate paths to be robust on Railway/CWD quirks
    candidates = [
        INDEX_HTML,
        STATIC_DIR / "index.html",
        Path("static") / "index.html",
        Path("/app/static/index.html"),
        BASE_DIR / "static" / "index.html",
    ]
    for p in candidates:
        try:
            if Path(p).exists():
                return FileResponse(str(p))
        except Exception:
            continue
    # If nothing found, return helpful diagnostics
    details = "<br>".join(str(Path(p).resolve()) for p in candidates)
    return HTMLResponse(
        "<h1>GanadoBravo</h1><p>Sube el frontend en <code>/static/index.html</code></p>"
        f"<p><small>No se encontró index.html en:<br>{details}</small></p>",
        status_code=200
    )

@app.get("/", response_class=HTMLResponse)
async def root():
    return RedirectResponse(url="/static/index.html", status_code=307)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/", response_class=HTMLResponse)
async def root():
    try:
        if INDEX_HTML.exists():
            return FileResponse(str(INDEX_HTML))
    except Exception:
        pass
    html = '<!doctype html>\n<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">\n<title>GanadoBravo</title></head><body style="font-family:system-ui,Segoe UI,Roboto,Helvetica,Arial,sans-serif;padding:24px;max-width:780px;margin:auto;">\n<h1>GanadoBravo</h1>\n<p>No se encontró <code>static/index.html</code> dentro del contenedor.</p>\n<ul>\n  <li><strong>Ruta esperada:</strong> {{index_path}}</li>\n  <li><strong>Directorio actual:</strong> {{cwd}}</li>\n  <li><strong>Contenido de /app:</strong> ver <a href="/_debug/static-list">/_debug/static-list</a></li>\n</ul>\n<p>Si el frontend y backend están en servicios distintos, asegúrate de publicar el UI en este mismo servicio, o ajusta el dominio del API en el meta <code>api-base</code> del HTML.</p>\n</body></html>'
    html = html.replace("{index_path}", str(INDEX_HTML)).replace("{cwd}", os.getcwd())
    return HTMLResponse(html, status_code=200)

@app.get("/_debug/static-list", response_class=HTMLResponse)
async def debug_static():
    try_paths = [
        str(INDEX_HTML),
        str(STATIC_DIR / "index.html"),
        "static/index.html",
        "/app/static/index.html",
    ]
    def ls(path):
        try:
            from pathlib import Path
            p = Path(path)
            if p.is_dir():
                items = [f"{'d' if x.is_dir() else 'f'}\t{x.name}" for x in p.iterdir()]
                return "<br>".join(items) if items else "(vacío)"
            elif p.is_file():
                return "(archivo presente)"
            else:
                return "(no existe)"
        except Exception as e:
            return f"(error: {e})"
    html = "<h2>Debug static/index.html</h2>"
    html += "<p><b>CWD:</b> " + os.getcwd() + "</p>"
    html += "<p><b>BASE_DIR:</b> " + str(BASE_DIR) + "</p>"
    html += "<ul>"
    for tp in try_paths:
        html += f"<li><code>{tp}</code>: {ls(Path(tp).parent)}</li>"
    html += "</ul>"
    html += "<p><a href='/'>volver</a></p>"
    return HTMLResponse(html)

@app.get("/", response_class=HTMLResponse)
async def root():
    try:
        with open(INDEX_HTML, "r", encoding="utf-8") as f:
            html = f.read()
        return HTMLResponse(html, status_code=200)
    except Exception as e:
        return HTMLResponse(f"<h1>GanadoBravo</h1><p>Error leyendo index: {e}</p>", status_code=200)
