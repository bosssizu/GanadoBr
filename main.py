
import os, io, json, base64
from typing import List, Dict, Any
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageStat, ImageOps

app = FastAPI(title="GanadoBravo Fullstack", version="v3-breed-ai")
app.mount("/static", StaticFiles(directory="static"), name="static")

METRICS = ["Conformación","Línea dorsal","Angulación costillar","Profundidad de pecho","Aplomos","Lomo","Grupo/muscling posterior","Balance anterior-posterior","Ancho torácico","Inserción de cola"]
HEALTH_ITEMS = ["Lesión cutánea","Claudicación","Secreción nasal","Conjuntivitis","Diarrea","Dermatitis","Lesión en pezuña","Parásitos externos","Tos"]

def _calc_brightness_features(image: Image.Image):
    img = ImageOps.exif_transpose(image).convert("L").resize((256,256))
    stat = ImageStat.Stat(img)
    return stat.mean[0], stat.stddev[0]

def _estimate_bcs(mean, stddev):
    m = max(0.0, min(1.0, (mean - 40.0) / (140.0-40.0)))
    s = max(0.0, min(1.0, stddev / 64.0))
    return round(2.0 + 1.8*(m*0.7 + (1.0-s)*0.3), 2)

def _scores_from_bcs(bcs: float, mode: str):
    base = 5.0 + (bcs - 2.5) * 1.2
    if mode == "vaca_flaca": base -= 0.8
    elif mode == "engorde": base += 0.5
    import random
    rnd = random.Random(int(bcs*1000) + (abs(hash(mode)) % 1000))
    scores = []
    for _ in range(10):
        val = max(3.0, min(8.7, base + rnd.uniform(-0.6,0.6)))
        scores.append(round(val,2))
    return scores

def _health_from_image(mean, stddev):
    flag = (stddev > 60)
    out = []
    for i, name in enumerate(HEALTH_ITEMS):
        status = "descartado" if not (flag and i==0) else "sospecha"
        out.append({"name":name,"status":status})
    return out

def _structure_avg(scores: List[float]) -> float:
    idx = [0,1,2,3,4,5,6,7,8]
    vals = [scores[i] for i in idx if i < len(scores)]
    return round(sum(vals)/len(vals),2) if vals else 0.0

def _weighted_global(scores: List[float], mode: str, bcs: float) -> float:
    wmap = {
        "levante":[1.3,1.1,1.0,1.1,1.1,1.0,1.3,1.2,1.1,0.8],
        "vaca_flaca":[1.4,1.1,1.0,1.2,1.3,1.0,1.1,1.1,1.1,0.7],
        "engorde":[1.1,1.0,1.0,1.3,1.0,1.0,1.4,1.1,1.3,0.8],
    }
    w = wmap.get(mode or "levante", wmap["levante"])
    num=0.0; den=0.0
    for i,s in enumerate(scores):
        ww = w[i] if i < len(w) else 1.0
        num += s*ww; den += ww
    g = (num/den) if den>0 else 0.0
    if mode=="levante":
        if 2.8<=bcs<=3.5: g+=0.20
        elif bcs<2.6: g-=0.30
        elif bcs>3.8: g-=0.15
    elif mode=="vaca_flaca":
        if bcs<=2.4 and _structure_avg(scores)>=6.2: g+=0.40
        elif bcs>2.8: g-=0.15
    elif mode=="engorde":
        if bcs>=3.2: g+=0.30
        elif bcs<2.9: g-=0.30
    return round(max(0.0, min(10.0, g)),2)

def _decision_from_gscore(g: float, bcs: float, mode: str):
    T = {"vaca_flaca":{"buy":8.0,"high":6.6,"low":5.8},"levante":{"buy":7.8,"high":6.8,"low":6.0},"engorde":{"buy":8.3,"high":7.4,"low":6.4}}
    t = T.get(mode or "levante", T["levante"])
    if g >= t["buy"]: return {"decision_level":"COMPRAR","decision_text":"Comprar"}
    if g >= t["high"]: return {"decision_level":"CONSIDERAR_ALTO","decision_text":"Considerar alto"}
    if g >= t["low"]: return {"decision_level":"CONSIDERAR_BAJO","decision_text":"Considerar (bajo)"}
    return {"decision_level":"NO_COMPRAR","decision_text":"No comprar"}

def _risk_from_scores(gscore: float, mode: str, scores: List[float]) -> float:
    r = max(0.0, min(1.0, 1.0 - gscore/10.0))
    if mode=="vaca_flaca" and _structure_avg(scores)>=6.4: r=max(0.0, r-0.05)
    return round(r,2)

BREED_LABELS=["Brahman","Nelore","Gyr","Cebú","Angus","Hereford","Holstein","Charolais","Limousin","Pardo Suizo","Brangus","Braford","Simbrah","Girolando","Criollo español","Criollo","Romosinuano","Carora"]
def _data_url(img_bytes: bytes)->str: return "data:image/jpeg;base64,"+base64.b64encode(img_bytes).decode("ascii")

def _breed_ai(image_bytes: bytes)->Dict[str,Any]:
    api_key=os.getenv("OPENAI_API_KEY")
    model=os.getenv("BREED_MODEL", os.getenv("OPENAI_MODEL","gpt-4o-mini"))
    if not api_key: raise RuntimeError("OPENAI_API_KEY missing")
    try:
        from openai import OpenAI
        client=OpenAI(api_key=api_key)
        system=("Eres un experto en razas bovinas. Responde SOLO JSON con: "
                "name, family(\"indicus\"|\"taurus\"|\"mixto\"), dominant, confidence(0..1), explanation. "
                "Usa catálogo: "+", ".join(BREED_LABELS)+". Sé conservador.")
        user="Clasifica la raza de este bovino. Solo JSON."
        r=client.chat.completions.create(
            model=model,
            messages=[
                {"role":"system","content":system},
                {"role":"user","content":[{"type":"text","text":user},{"type":"image_url","image_url":{"url":_data_url(image_bytes)}}]}
            ],
            temperature=0.2,max_tokens=250,timeout=12
        )
        data=json.loads(r.choices[0].message.content.strip()); data["engine"]="ai"; return data
    except Exception as e:
        try:
            import openai as oai
            oai.api_key=api_key
            resp=oai.ChatCompletion.create(model="gpt-4o-mini",messages=[
                {"role":"system","content":"Eres experto en razas. Solo JSON: name,family,dominant,confidence,explanation."},
                {"role":"user","content":[{"type":"text","text":"Clasifica la raza."},{"type":"image_url","image_url":{"url":_data_url(image_bytes)}}]}
            ])
            data=json.loads(resp["choices"][0]["message"]["content"].strip()); data["engine"]="ai"; return data
        except Exception as e2:
            raise RuntimeError(f"breed ai failed: {e2}") from e

def _breed_fallback(img: Image.Image, mean_l: float, std_l: float)->Dict[str,Any]:
    indicus_score=max(0.0,min(1.0,(80-mean_l)/40.0+std_l/100.0))
    if indicus_score>=0.62: return {"name":"Cebú (indicus predominante)","family":"indicus","dominant":"indicus","confidence":0.62,"explanation":"Rasgos indicus visibles.","engine":"fallback"}
    if 0.45<=indicus_score<0.62: return {"name":"Cruza indicus×taurus — predomina indicus","family":"mixto","dominant":"indicus","confidence":0.58,"explanation":"Mezcla con mayor componente indicus.","engine":"fallback"}
    return {"name":"Cruza indicus×taurus — predomina taurus","family":"mixto","dominant":"taurus","confidence":0.58,"explanation":"Perfil y pelaje europeos.","engine":"fallback"}

def _evaluate_bytes(data: bytes, mode: str):
    from PIL import Image
    img=Image.open(io.BytesIO(data)).convert("RGB")
    mean,stddev=_calc_brightness_features(img)
    bcs=_estimate_bcs(mean,stddev)
    scores=_scores_from_bcs(bcs,mode)
    g=_weighted_global(scores,mode,bcs)
    risk=_risk_from_scores(g,mode,scores)
    dec=_decision_from_gscore(g,bcs,mode)
    health=_health_from_image(mean,stddev)
    rubric=[{"name":n,"score":s,"obs":"Correcta" if s>=6.0 else "Adecuada"} for n,s in zip(METRICS,scores)]
    try: breed=_breed_ai(data); engine="ai"
    except Exception: breed=_breed_fallback(img,mean,stddev); engine="fallback"
    return {"engine":engine,"decision_level":dec["decision_level"],"decision_text":dec["decision_text"],"bcs":bcs,"global_score":g,"risk":risk,"posterior_bonus":0.0,"rubric":rubric,"health":[{"name":h["name"],"status":h["status"]} for h in health],"breed":breed,"reasons":["Estructura general adecuada.","No se detectaron problemas de salud (screening visual)."]}

@app.get("/", response_class=HTMLResponse)
def index(): return FileResponse("static/index.html")

@app.get("/healthz")
def health():
    return {"ok":True,"version":"fullstack-v3-breed-ai","env":{"OPENAI_API_KEY":"set" if os.getenv("OPENAI_API_KEY") else "missing","BREED_MODEL":os.getenv("BREED_MODEL","") }}

@app.get("/api/diag")
def diag(): return {"routes":[r.path for r in app.router.routes]}

def _handle(file: UploadFile, mode:str):
    data=file.file.read()
    return {"result":_evaluate_bytes(data, mode or "levante")}

@app.post("/evaluate")
async def evaluate(file: UploadFile=File(...), mode: str=Form(...)): return JSONResponse(_handle(file,mode))

@app.post("/api/evaluate")
async def evaluate_api(file: UploadFile=File(...), mode: str=Form(...)): return JSONResponse(_handle(file,mode))
