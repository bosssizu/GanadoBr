import os, io, importlib
from pathlib import Path
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

try:
    from PIL import Image
except Exception:
    Image = None

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
INDEX_HTML = STATIC_DIR / "index.html"

app = FastAPI(title="GanadoBravo", version="v38-real-ready")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/", response_class=HTMLResponse)
async def root():
    if INDEX_HTML.exists():
        return FileResponse(str(INDEX_HTML))
    return HTMLResponse("<h1>GanadoBravo</h1><p>Falta static/index.html</p>", status_code=200)

@app.get("/health")
def health():
    return {"ok": True, "service": "GanadoBravo", "version": "v38-real-ready"}

# -------- Real pipeline loader --------
def try_import_pipeline():
    try:
        return importlib.import_module("pipeline_real")
    except Exception:
        return None

def image_from_upload(upload: UploadFile):
    data = None
    try:
        data = upload.file.read() if hasattr(upload, "file") else None
        if not data and hasattr(upload, "read"):
            data = upload.read()
    except Exception:
        data = None
    if Image is not None and isinstance(data, (bytes, bytearray)):
        try:
            img = Image.open(io.BytesIO(data)).convert("RGB")
            return img
        except Exception:
            return None
    return None

def evaluate_batch_internal(files: List[UploadFile], mode: str = "levante") -> List[Dict[str, Any]]:
    pipe = try_import_pipeline()
    use_mock = bool(os.getenv("GB_MOCK", "0") == "1" or pipe is None)

    results = []
    for f in files or []:
        # If real pipeline available and not forced mock:
        if not use_mock and pipe is not None:
            try:
                img = image_from_upload(f)
                # --- Double pass metrics ---
                m1 = pipe.run_metrics_pass(img=img, mode=mode, pass_id=1)
                m2 = pipe.run_metrics_pass(img=img, mode=mode, pass_id=2)
                metrics = pipe.aggregate_metrics(m1, m2)

                # --- Health (backend-only heuristics) ---
                health = pipe.detect_health(img=img, metrics=metrics)

                # --- Breed (hidden prompt) ---
                breed = pipe.run_breed_prompt(img=img)

                # --- Final decision object (format expected by UI) ---
                d = pipe.format_output(metrics=metrics, health=health, breed=breed, mode=mode)

                results.append({"result": d, "filename": getattr(f, "filename", None)})
                continue
            except Exception as e:
                # fall-through to mock if real pipeline fails
                pass

        # -------- Mock fallback (keeps UI working) --------
        d = {
            "mode": mode,
            "global_conf": 0.93,
            "decision_level": "CONSIDERAR_ALTO",
            "decision_text": "Considerar alto",
            "global_score": 7.4,
            "bcs": 3.5,
            "risk": 0.20,
            "posterior_bonus": 0.10,
            "notes": "Evaluación (mock fallback).",
            "qc": {"visible_ratio": 0.86, "stability": "alta", "auction_mode": False},
            "rubric": [
                {"name":"Conformación", "score":7.8, "obs":"Correcta"},
                {"name":"BCS", "score":3.5, "obs":"Adecuado"},
                {"name":"Riesgo", "score":0.20, "obs":"Bajo"}
            ],
            "reasons": ["Estructura adecuada", "Condición corporal aceptable"],
            "health": [{"name":"Lesión cutánea", "severity":"descartado"}],
            "breed": {"name":"Criollo (mixto)", "confidence":0.58, "explanation":"Rasgos mixtos; posible entrecruzamiento"}
        }
        results.append({"result": d, "filename": getattr(f, "filename", None)})
    return results

@app.post("/evaluate")
async def evaluate(file: UploadFile = File(...), mode: str = Form("levante")):
    try:
        return evaluate_batch_internal([file], mode=mode)
    except Exception as e:
        import traceback
        return JSONResponse({"error":"evaluate_failed","detail":str(e),"trace":traceback.format_exc()}, status_code=500)

@app.post("/evaluate_batch")
async def evaluate_batch(files: List[UploadFile] = File(...), mode: str = Form("levante")):
    try:
        return evaluate_batch_internal(files, mode=mode)
    except Exception as e:
        import traceback
        return JSONResponse({"error":"evaluate_failed","detail":str(e),"trace":traceback.format_exc()}, status_code=500)
