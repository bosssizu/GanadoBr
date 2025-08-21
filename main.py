import os, io
from pathlib import Path
from typing import List
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
app = FastAPI(title="GanadoBravo", version="v37")
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
    return {"ok": True, "service": "GanadoBravo", "version": "v37"}
def evaluate_batch_internal(files: List[UploadFile], mode: str = "levante"):
    results = []
    for f in files or []:
        filename = getattr(f, "filename", None)
        try:
            if Image is not None:
                data = f.file.read() if hasattr(f, "file") else None
                if not data and hasattr(f, "read"):
                    data = f.read()
                if isinstance(data, bytes):
                    img = Image.open(io.BytesIO(data)); img.verify()
        except Exception:
            pass
        d = {
            "mode": mode,
            "global_conf": 0.93,
            "decision_level": "CONSIDERAR_ALTO",
            "decision_text": "Considerar alto",
            "global_score": 7.4,
            "bcs": 3.5,
            "risk": 0.20,
            "posterior_bonus": 0.10,
            "notes": "Evaluación base (mock).",
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
        results.append({"result": d, "filename": filename})
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
