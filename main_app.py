
import os, asyncio, time
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

APP_VERSION = "v40i-fallback-fix"

app = FastAPI(title="GanadoBravo API", version=APP_VERSION)
LAST_ERROR = None
LAST_RESULT = None
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
        "ENABLE_BREED": os.getenv("ENABLE_BREED","1"),
        "OPENAI_MODEL": os.getenv("OPENAI_MODEL","gpt-4o-mini"),
        "BREED_MODEL": os.getenv("BREED_MODEL","gpt-4o-mini"),
    }, "last_error": LAST_ERROR, "last_result_set": LAST_RESULT is not None}

MAX_IMAGE_MB = int(os.getenv("MAX_IMAGE_MB","8"))
WATCHDOG_SECONDS = int(os.getenv("WATCHDOG_SECONDS","20"))

async def _evaluate_internal(img_bytes: bytes, mode: str):
    global LAST_ERROR
    try:
        from pipeline_real import run_rubric_timeboxed, detect_health, run_breed_prompt, format_output
        t0 = time.time()
        agg = run_rubric_timeboxed(img_bytes, mode)
        health = detect_health(img_bytes, agg)
        breed = run_breed_prompt(img_bytes)
        out = format_output(agg, health, breed, mode)
        out["debug"] = {"latency_ms": int((time.time()-t0)*1000)}
        LAST_ERROR = None
LAST_RESULT = None
        return out
    except Exception as e:
        import traceback
        LAST_ERROR = {"error": str(e), "trace": traceback.format_exc()[-1200:]}
        return {"status":"error","code":500,"message":"pipeline exception","detail":str(e)}

@app.post("/evaluate")
async def evaluate(file: UploadFile = File(...), mode: str = Form("levante")):
    img_bytes = await file.read()
    if not img_bytes:
        raise HTTPException(status_code=400, detail="Archivo vacío")
    if len(img_bytes) > MAX_IMAGE_MB*1024*1024:
        raise HTTPException(status_code=413, detail=f"Imagen supera {MAX_IMAGE_MB} MB")
    try:
        res = await asyncio.wait_for(_evaluate_internal(img_bytes, mode), timeout=WATCHDOG_SECONDS)
        status = 200 if "decision_level" in res else 200
        return JSONResponse(res, status_code=status)
    except asyncio.TimeoutError:
        return JSONResponse({"status":"error","code":504,"message":"watchdog timeout"}, status_code=504)

@app.get("/evaluate")
def evaluate_get_hint():
    return JSONResponse({"status":"error","message":"Use POST /evaluate con archivo 'file' y campo 'mode'."}, status_code=405)

from fastapi import Request
@app.get("/{path:path}", response_class=HTMLResponse)
def catch_all(path: str):
    if path.startswith("api") or path.startswith("static"):
        return JSONResponse({"detail":"Not Found"}, status_code=404)
    return FileResponse(os.path.join(static_dir, "index.html"))


from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse({"status":"error","code":exc.status_code,"message":exc.detail}, status_code=exc.status_code)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse({"status":"error","code":422,"message":"validation error","detail":exc.errors()}, status_code=422)


@app.get("/api/last")
def last():
    return {"ok": True, "result": LAST_RESULT}
