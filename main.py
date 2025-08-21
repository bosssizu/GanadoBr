from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
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

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

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
async def evaluate_batch(files: List[UploadFile] = File(...), mode: str = Form("levante")):
    results = []
    cfg = _cfg()
    for f in files:
        try:
            raw = await f.read()
            img = Image.open(io.BytesIO(raw)).convert("RGB")
        except Exception:
            results.append({"filename": f.filename, "error":"imagen inválida"})
            continue
        d: Dict[str, Any] = {"mode": mode, "qc": {}, "reasons": []}
        vis_ratio = _estimate_visible_ratio(img)
        d["qc"]["visible_ratio"] = round(vis_ratio, 2)
        d["qc"]["auction_mode"] = (vis_ratio < 0.55) or (mode == "auction")
        d["raw_image"] = img
        warn = _validate_input(img)
        for w in warn:
            d["reasons"].append(w)
        first = run_auction_heuristics(img)
        d = apply_heuristic_scoring(d, first)
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
        results.append({"filename": f.filename, "result": d})
    return JSONResponse(results)


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
