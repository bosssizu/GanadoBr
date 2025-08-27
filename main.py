
import os, asyncio, time
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

from pipeline_real import run_rubric_timeboxed, detect_health, run_breed_prompt, format_output

APP_VERSION = "v39s-strict-modes"

app = FastAPI(title="GanadoBravo API", version=APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

LAST_ERROR = {"when": None, "where": None, "msg": None}

@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse(os.path.join(static_dir, "index.html"))

@app.get("/api/diag")
def diag():
    return {
        "ok": True,
        "version": APP_VERSION,
        "env": {
            "ENABLE_AI_RUBRIC": os.getenv("ENABLE_AI_RUBRIC","1"),
            "ENABLE_BREED": os.getenv("ENABLE_BREED","1"),
            "LLM_PROVIDER": os.getenv("LLM_PROVIDER","openai"),
            "OPENAI_MODEL": os.getenv("OPENAI_MODEL","gpt-4o-mini"),
            "BREED_MODEL": os.getenv("BREED_MODEL","gpt-4o-mini"),
            "LLM_TIMEOUT_SEC": int(os.getenv("LLM_TIMEOUT_SEC","7")),
            "BREED_TIMEOUT_SEC": int(os.getenv("BREED_TIMEOUT_SEC","6")),
            "LLM_RETRIES": int(os.getenv("LLM_RETRIES","0")),
            "TIME_BUDGET_SEC": int(os.getenv("TIME_BUDGET_SEC","9")),
            "WATCHDOG_SECONDS": int(os.getenv("WATCHDOG_SECONDS","20")),
        },
        "last_error": LAST_ERROR,
    }

MAX_IMAGE_MB = int(os.getenv("MAX_IMAGE_MB","8"))
WATCHDOG_SECONDS = int(os.getenv("WATCHDOG_SECONDS","20"))

async def _evaluate_internal(img_bytes: bytes, mode: str):
    t0 = time.time()
    agg = run_rubric_timeboxed(img_bytes, mode)
    health = detect_health(img_bytes, agg)
    breed = run_breed_prompt(img_bytes)  # AI breed
    out = format_output(agg, health, breed, mode)
    out["debug"] = {"latency_ms": int((time.time()-t0)*1000), "ai_used": agg.get("notes","").startswith("ai_")}
    return out

@app.post("/evaluate")
async def evaluate_compat(request: Request, file: UploadFile = File(...), mode: str = Form("levante")):
    img_bytes = await file.read()
    if not img_bytes:
        raise HTTPException(status_code=400, detail="Archivo vacío")
    if len(img_bytes) > MAX_IMAGE_MB*1024*1024:
        raise HTTPException(status_code=413, detail=f"Imagen supera {MAX_IMAGE_MB} MB")
    try:
        res = await asyncio.wait_for(_evaluate_internal(img_bytes, mode), timeout=WATCHDOG_SECONDS)
        return JSONResponse(res)
    except asyncio.TimeoutError:
        return JSONResponse({"status":"error","code":504,"message":"watchdog timeout"}, status_code=504)

@app.post("/api/eval")
async def evaluate_api(request: Request, file: UploadFile = File(...), mode: str = Form("levante")):
    return await evaluate_compat(request, file, mode)
