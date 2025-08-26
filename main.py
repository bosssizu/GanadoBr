
import os, io, importlib, base64
from pathlib import Path
from typing import List, Dict, Any

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

try:
    from PIL import Image
except Exception:
    Image = None

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="GanadoBravo", version="v39-full")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ----------------------------------------------------
# Helpers
# ----------------------------------------------------
def try_import_pipeline():
    try:
        return importlib.import_module("pipeline_real")
    except Exception:
        return None

def image_from_upload(upload: UploadFile):
    if Image is None:
        return None
    data = upload.file.read()
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
        return img
    except Exception:
        return None

def img_preview_base64(img):
    if img is None or Image is None:
        return None
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return "data:image/jpeg;base64," + b64

# ----------------------------------------------------
# Routes
# ----------------------------------------------------
@app.get("/")
def index():
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html)

@app.get("/health")
def health():
    return {"ok": True, "service":"GanadoBravo", "version":"v39-full"}

def evaluate_internal(files: List[UploadFile], mode: str = "levante"):
    pipe = try_import_pipeline()
    use_mock = bool(os.getenv("GB_MOCK", "0") == "1" or pipe is None)

    results = []
    for f in files or []:
        if not use_mock and pipe is not None:
            try:
                img = image_from_upload(f)
                m1 = pipe.run_metrics_pass(img=img, mode=mode, pass_id=1)
                m2 = pipe.run_metrics_pass(img=img, mode=mode, pass_id=2)
                metrics = pipe.aggregate_metrics(m1, m2)
                health = pipe.detect_health(img=img, metrics=metrics)
                breed  = pipe.run_breed_prompt(img=img)
                payload = pipe.format_output(metrics=metrics, health=health, breed=breed, mode=mode)
            except Exception as ex:
                payload = {"error":"pipeline_failed", "detail":str(ex)}
        else:
            # Safe mock minimal payload (should not be used when pipeline_real exists)
            payload = {
                "decision_level": "CONSIDERAR_ALTO",
                "decision_text": "Considerar alto",
                "global_score": 7.4,
                "bcs": 3.5,
                "risk": 0.20,
                "posterior_bonus": 0.10,
                "notes": "Evaluación (mock fallback).",
                "qc": {"visible_ratio": 0.86, "stability": "alta", "auction_mode": (mode=="subasta")},
                "rubric": [
                    {"name":"Conformación", "score":7.8, "obs":"Correcta"},
                    {"name":"BCS", "score":3.5, "obs":"Adecuado"},
                    {"name":"Riesgo", "score":0.20, "obs":"Bajo"}
                ],
                "reasons": ["Estructura adecuada", "Condición corporal aceptable"],
                "health": [{"name":"Lesión cutánea", "severity":"descartado"}],
                "breed": {"name":"Criollo (mixto)", "confidence":0.58, "explanation":"Rasgos mixtos; posible entrecruzamiento"}
            }
        # Include a preview so UI can show the selected image
        try:
            img = image_from_upload(f)
            payload["preview"] = img_preview_base64(img)
        except Exception:
            pass
        results.append({"result": payload, "filename": getattr(f, "filename", None)})
    return results

@app.post("/evaluate")
async def evaluate(file: UploadFile = File(...), mode: str = Form("levante")):
    return evaluate_internal([file], mode=mode)

@app.post("/evaluate_batch")
async def evaluate_batch(files: List[UploadFile] = File(...), mode: str = Form("levante")):
    return evaluate_internal(files, mode=mode)
