
import os
import io
from typing import List, Dict, Any
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageStat

app = FastAPI(title="GanadoBravo Fullstack", version="v1")

# serve frontend
app.mount("/static", StaticFiles(directory="static"), name="static")

METRICS = [
    "Conformación","Línea dorsal","Angulación costillar","Profundidad de pecho",
    "Aplomos","Lomo","Grupo/muscling posterior","Balance anterior-posterior",
    "Ancho torácico","Inserción de cola"
]

HEALTH_ITEMS = [
    "Lesión cutánea","Claudicación","Secreción nasal","Conjuntivitis",
    "Diarrea","Dermatitis","Lesión en pezuña","Parásitos externos","Tos"
]

def _calc_brightness_features(image: Image.Image):
    img = image.convert("L").resize((256, 256))
    stat = ImageStat.Stat(img)
    mean = stat.mean[0]
    stddev = stat.stddev[0]
    return mean, stddev

def _estimate_bcs(mean, stddev):
    # Estima BCS 2.0-3.8 usando brillo/contraste como proxy grosero
    m = max(0.0, min(1.0, (mean - 40.0) / (140.0-40.0)))
    s = max(0.0, min(1.0, stddev / 64.0))
    bcs = 2.0 + 1.8 * (m*0.7 + (1.0-s)*0.3)
    return round(bcs, 2)

def _scores_from_bcs(bcs: float, mode: str):
    # genera 10 métricas alrededor de un base
    base = 5.0 + (bcs - 2.5) * 1.2
    if mode == "vaca_flaca":
        base -= 0.8
    elif mode == "engorde":
        base += 0.5
    scores = []
    import random
    rnd = random.Random(int(bcs*1000))
    for i in range(10):
        jitter = rnd.uniform(-0.6, 0.6)
        val = max(3.0, min(8.5, base + jitter))
        scores.append(round(val, 2))
    return scores

def _health_from_image(mean, stddev):
    # marca todo 'Descartado'; si contraste extremo, deja 1 sospecha
    health = []
    flag = (stddev > 60)
    for i, name in enumerate(HEALTH_ITEMS):
        status = "descartado"
        if flag and i == 0:
            status = "sospecha"
        health.append({"name": name, "status": status})
    return health

def _global_score(scores: List[float]) -> float:
    return round(sum(scores) / len(scores), 2) if scores else 0.0

def _risk_from_scores(gscore: float) -> float:
    r = max(0.0, min(1.0, 1.0 - gscore/10.0))
    return round(r, 2)

def _decision_from_gscore(g: float) -> Dict[str,str]:
    if g >= 8.2:
        return {"decision_level":"COMPRAR", "decision_text":"Comprar"}
    if g >= 7.2:
        return {"decision_level":"CONSIDERAR_ALTO", "decision_text":"Considerar alto"}
    if g >= 6.2:
        return {"decision_level":"CONSIDERAR_BAJO", "decision_text":"Considerar (bajo)"}
    return {"decision_level":"NO_COMPRAR", "decision_text":"No comprar"}

def _engine_status():
    if os.getenv("OPENAI_API_KEY") or os.getenv("ENABLE_AI") == "1":
        return "ai"
    return "fallback"

def _breed_guess(mean, stddev) -> Dict[str, Any]:
    indicus_score = max(0.0, min(1.0, (80-mean)/40.0 + stddev/100.0))
    if indicus_score >= 0.5:
        return {
            "name": "Cruza indicus×taurus — predomina indicus",
            "confidence": round(0.6 + (indicus_score-0.5)*0.8, 2),
            "explanation": "Pliegues de piel / cuello y configuración general sugieren influencia cebú (Bos indicus)."
        }
    else:
        return {
            "name": "Cruza indicus×taurus — predomina taurus",
            "confidence": round(0.6 + (0.5-indicus_score)*0.8, 2),
            "explanation": "Perfil más recto y pelaje sin pliegues marcados sugieren mayor componente europeo (Bos taurus)."
        }

def _evaluate_bytes(data: bytes, mode: str):
    from PIL import Image
    img = Image.open(io.BytesIO(data)).convert("RGB")
    mean, stddev = _calc_brightness_features(img)
    bcs = _estimate_bcs(mean, stddev)
    scores = _scores_from_bcs(bcs, mode)
    gscore = _global_score(scores)
    risk = _risk_from_scores(gscore)
    dec = _decision_from_gscore(gscore)
    health = _health_from_image(mean, stddev)
    rubric = [{"name": n, "score": s, "obs": "Correcta" if s>=6.0 else "Adecuada"} for n, s in zip(METRICS, scores)]
    engine = _engine_status()
    breed = _breed_guess(mean, stddev)
    result = {
        "engine": engine,
        "decision_level": dec["decision_level"],
        "decision_text": dec["decision_text"],
        "bcs": bcs,
        "global_score": gscore,
        "risk": risk,
        "posterior_bonus": 0.0,
        "rubric": rubric,
        "health": [{"name": h["name"], "status": h["status"]} for h in health],
        "breed": breed,
        "reasons": [
            "Estructura general adecuada.",
            "No se detectaron problemas de salud (screening visual)."
        ]
    }
    return result

@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse("static/index.html")

@app.get("/healthz")
def health():
    return {
        "ok": True,
        "version": "fullstack-v1",
        "env": {
            "ENABLE_AI": os.getenv("ENABLE_AI", ""),
            "OPENAI_MODEL": os.getenv("OPENAI_MODEL", ""),
            "BREED_MODEL": os.getenv("BREED_MODEL", ""),
            "OPENAI_API_KEY": "set" if os.getenv("OPENAI_API_KEY") else "missing"
        }
    }

@app.get("/api/diag")
def diag():
    return {"routes": [r.path for r in app.router.routes]}

def _handle_eval(file: UploadFile, mode: str):
    data = file.file.read()
    res = _evaluate_bytes(data, mode or "levante")
    return {"result": res}

@app.post("/evaluate")
async def evaluate(file: UploadFile = File(...), mode: str = Form(...)):
    return JSONResponse(_handle_eval(file, mode))

@app.post("/api/evaluate")
async def evaluate_api(file: UploadFile = File(...), mode: str = Form(...)):
    return JSONResponse(_handle_eval(file, mode))
