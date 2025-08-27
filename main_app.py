
import os, asyncio, time
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

APP_VERSION = "v39x-lazyimport-fix"

app = FastAPI(title="GanadoBravo API", version=APP_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse(os.path.join(static_dir, "index.html"))

@app.get("/healthz")
def healthz():
    return {"ok": True, "version": APP_VERSION}

@app.get("/routes")
def routes():
    return [{"path": r.path, "name": getattr(r.app, "__name__", None)} for r in app.router.routes]

@app.get("/api/diag")
def diag():
    return {"ok": True, "version": APP_VERSION, "env": {
        "ENABLE_AI_RUBRIC": os.getenv("ENABLE_AI_RUBRIC","1"),
        "ENABLE_BREED": os.getenv("ENABLE_BREED","1"),
        "LLM_PROVIDER": os.getenv("LLM_PROVIDER","openai"),
        "OPENAI_MODEL": os.getenv("OPENAI_MODEL","gpt-4o-mini"),
        "BREED_MODEL": os.getenv("BREED_MODEL","gpt-4o-mini"),
    }}

MAX_IMAGE_MB = int(os.getenv("MAX_IMAGE_MB","8"))
WATCHDOG_SECONDS = int(os.getenv("WATCHDOG_SECONDS","20"))

async def _evaluate_internal(img_bytes: bytes, mode: str):
    # Lazy import backend to avoid import-time crashes breaking the app
    try:
        from pipeline_real import run_rubric_timeboxed, detect_health, run_breed_prompt, format_output
    except Exception as e:
        return {"status":"error","code":500,"message":"Backend import failed","detail":str(e)}
    import asyncio, time
    t0 = time.time()
    agg = run_rubric_timeboxed(img_bytes, mode)
    health = detect_health(img_bytes, agg)
    breed = run_breed_prompt(img_bytes)
    out = format_output(agg, health, breed, mode)
    out["debug"] = {"latency_ms": int((time.time()-t0)*1000), "ai_used": agg.get("notes","").startswith("ai_")}
    return out

@app.post("/evaluate")
async def evaluate(file: UploadFile = File(...), mode: str = Form("levante")):
    img_bytes = await file.read()
    if not img_bytes:
        raise HTTPException(status_code=400, detail="Archivo vacío")
    if len(img_bytes) > MAX_IMAGE_MB*1024*1024:
        raise HTTPException(status_code=413, detail=f"Imagen supera {MAX_IMAGE_MB} MB")
    try:
        res = await asyncio.wait_for(_evaluate_internal(img_bytes, mode), timeout=WATCHDOG_SECONDS)
        status = 200 if "decision_level" in res else 500
        return JSONResponse(res, status_code=status)
    except asyncio.TimeoutError:
        return JSONResponse({"status":"error","code":504,"message":"watchdog timeout"}, status_code=504)

# Friendly 405 for GET /evaluate
@app.get("/evaluate")
def evaluate_get_hint():
    return JSONResponse({"status":"error","message":"Use POST /evaluate con archivo 'file' y campo 'mode'."}, status_code=405)

# Catch‑all: sirve index para rutas que no sean /api* ni /static*
from fastapi import Request
@app.get("/{path:path}", response_class=HTMLResponse)
def catch_all(path: str):
    if path.startswith("api") or path.startswith("static"):
        return JSONResponse({"detail":"Not Found"}, status_code=404)
    return FileResponse(os.path.join(static_dir, "index.html"))
