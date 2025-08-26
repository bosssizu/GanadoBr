import os, asyncio, sys, json, time
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

from pipeline_real import run_metrics_pass, aggregate_metrics, detect_health, run_breed_prompt, format_output

APP_VERSION = "v39f"

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

def log(*args):
    print("[GB]", *args, file=sys.stdout, flush=True)

@app.on_event("startup")
async def _startup():
    log("startup", {"version": APP_VERSION, "pid": os.getpid()})

@app.on_event("shutdown")
async def _shutdown():
    log("shutdown")

@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse(os.path.join(static_dir, "index.html"))

@app.get("/api/health")
def health():
    return {"ok": True, "version": APP_VERSION}

@app.get("/api/diag")
def diag():
    return {
        "ok": True,
        "version": APP_VERSION,
        "env": {
            "LLM_PROVIDER": os.getenv("LLM_PROVIDER","openai"),
            "BREED_DISABLED": os.getenv("BREED_DISABLED","(default)1"),
            "OPENAI_MODEL": os.getenv("OPENAI_MODEL","gpt-4o-mini"),
            "OPENAI_BASE_URL": bool(os.getenv("OPENAI_BASE_URL")),
            "AZURE_OPENAI_ENDPOINT": bool(os.getenv("AZURE_OPENAI_ENDPOINT")),
        },
        "last_error": LAST_ERROR,
    }

MAX_IMAGE_MB = int(os.getenv("MAX_IMAGE_MB","8"))
WATCHDOG_SECONDS = int(os.getenv("WATCHDOG_SECONDS","8"))  # límite duro por petición

async def _evaluate_internal(img_bytes: bytes, mode: str):
    t0 = time.time()
    m1 = run_metrics_pass(img_bytes, mode, pass_id=1)
    m2 = run_metrics_pass(img_bytes, mode, pass_id=2)
    agg = aggregate_metrics(m1, m2)
    health = detect_health(img_bytes, agg)
    breed = run_breed_prompt(img_bytes)  # contiene su propio timeout/fallback
    out = format_output(agg, health, breed, mode)
    out["debug"] = {"latency_ms": int((time.time()-t0)*1000)}
    return out

@app.post("/evaluate")
async def evaluate_compat(request: Request, file: UploadFile = File(...), mode: str = Form("levante")):
    rid = request.headers.get("X-Request-Id") or "no-rid"
    try:
        img_bytes = await file.read()
        if not img_bytes:
            raise HTTPException(status_code=400, detail="Archivo vacío")
        if len(img_bytes) > MAX_IMAGE_MB*1024*1024:
            raise HTTPException(status_code=413, detail=f"Imagen supera {MAX_IMAGE_MB} MB")
        log("eval_start", {"rid": rid, "size_kb": len(img_bytes)//1024, "mode": mode})
        # Watchdog: si se pasa del límite, respondemos 504 (mejor que 502 por timeout del proxy)
        resp = await asyncio.wait_for(_evaluate_internal(img_bytes, mode), timeout=WATCHDOG_SECONDS)
        log("eval_ok", {"rid": rid, "lat_ms": resp.get("debug",{}).get("latency_ms")})
        return JSONResponse(resp)
    except asyncio.TimeoutError:
        LAST_ERROR.update({"when": time.time(), "where": "/evaluate", "msg": "watchdog_timeout"})
        log("eval_timeout", {"rid": rid, "limit_s": WATCHDOG_SECONDS})
        return JSONResponse({"status":"error","code":504,"message":"watchdog timeout"}, status_code=504)
    except HTTPException as he:
        log("eval_http_exc", {"rid": rid, "status": he.status_code, "detail": he.detail})
        raise
    except Exception as e:
        LAST_ERROR.update({"when": time.time(), "where": "/evaluate", "msg": str(e)})
        log("eval_fail", {"rid": rid, "err": str(e)})
        return JSONResponse({"status":"error","code":500,"message":str(e)}, status_code=500)

@app.post("/api/eval")
async def evaluate_api(request: Request, file: UploadFile = File(...), mode: str = Form("levante")):
    return await evaluate_compat(request, file, mode)
