import os
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from time import time

from pipeline_real import run_metrics_pass, aggregate_metrics, detect_health, run_breed_prompt, format_output

app = FastAPI(title="GanadoBravo API", version="v39d")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse(os.path.join(static_dir, "index.html"))

@app.get("/api/health")
def health():
    return {"ok": True, "version": "v39d"}

MAX_IMAGE_MB = 8

def _evaluate_internal(img_bytes: bytes, mode: str):
    # Simple guard
    if len(img_bytes) > MAX_IMAGE_MB*1024*1024:
        raise HTTPException(status_code=413, detail=f"Imagen supera {MAX_IMAGE_MB} MB")
    t0 = time()
    m1 = run_metrics_pass(img_bytes, mode, pass_id=1)
    m2 = run_metrics_pass(img_bytes, mode, pass_id=2)
    agg = aggregate_metrics(m1, m2)
    health = detect_health(img_bytes, agg)
    breed = run_breed_prompt(img_bytes)  # non-blocking inside (fast fallback)
    out = format_output(agg, health, breed, mode)
    out["debug"] = {"latency_ms": int((time()-t0)*1000)}
    return out

@app.post("/evaluate")
async def evaluate_compat(file: UploadFile = File(...), mode: str = Form("levante")):
    img_bytes = await file.read()
    if not img_bytes:
        raise HTTPException(status_code=400, detail="Archivo vacío")
    return JSONResponse(_evaluate_internal(img_bytes, mode))

@app.post("/api/eval")
async def evaluate_api(file: UploadFile = File(...), mode: str = Form("levante")):
    return await evaluate_compat(file, mode)
