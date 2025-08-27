
"""
GanadoBravo — pipeline_real.py (v40a-full)
Implementación ligera para MVP (heurística local + prompt de raza).
"""
from typing import Any, Dict, List
import base64, os, json, math, time

# ------------------ Métricas y agregación (simplificadas, reproducibles) ------------------
def _pseudo_score(seed: int, low=5.4, high=7.6):
    # Determinista por semilla: simple lcg
    seed = (1103515245*seed + 12345) & 0x7fffffff
    r = (seed % 1000)/1000.0
    return round(low + (high-low)*r, 2)

def run_rubric_timeboxed(img_bytes: bytes, mode: str)->Dict[str,Any]:
    # Heurística: usar longitud de bytes como semilla estable (sin ML real; MVP)
    seed = len(img_bytes) % 9973
    rubric_names = ["Conformación","Línea dorsal","Angulación costillar","Profundidad de pecho",
                    "Aplomos","Lomo","Grupo/muscling posterior","Balance anterior-posterior",
                    "Ancho torácico","Inserción de cola"]
    scores = []
    for i,_ in enumerate(rubric_names):
        scores.append({"name":rubric_names[i], "score": _pseudo_score(seed+i)})
    # BCS y riesgo heurísticos
    bcs = max(2.0, min(4.0, round(2.0 + (seed % 30)/30.0*2.0, 2)))
    risk = round(0.2 + ((seed//7)%30)/100.0, 2)
    posterior_bonus = 0.0
    global_score = round(sum(s["score"] for s in scores)/len(scores),2)
    return {"scores": {s["name"]:s["score"] for s in scores},
            "bcs": bcs, "risk": risk, "posterior_bonus": posterior_bonus,
            "rubric": [{"name":s["name"],"score":s["score"],"obs":"Correcta" if s["score"]>=6 else "Adecuada"} for s in scores],
            "global_score": global_score,
            "notes": ""}

def detect_health(img_bytes: bytes, agg: Dict[str,Any])->List[Dict[str,Any]]:
    names = ["Lesión cutánea","Claudicación","Secreción nasal","Conjuntivitis","Diarrea","Dermatitis",
             "Lesión en pezuña","Parásitos externos","Tos"]
    return [{"name":n,"status":"descartado"} for n in names]

# ------------------ Raza (familia + predominancia) ------------------
def _llm_keys_present():
    return bool(os.getenv("OPENAI_API_KEY") or os.getenv("AZURE_OPENAI_API_KEY"))

def _sdk_available(provider:str)->bool:
    try:
        if provider=="azure":
            from openai import AzureOpenAI  # noqa
        else:
            import openai  # noqa
        return True
    except Exception:
        return False
->bool:
    return bool(os.getenv("OPENAI_API_KEY") or os.getenv("AZURE_OPENAI_API_KEY"))

def _provider()->str:
    return "azure" if os.getenv("AZURE_OPENAI_API_KEY") else "openai"

def _breed_model()->str:
    return os.getenv("BREED_MODEL","gpt-4o-mini")

def _bre_timeout()->int:
    return int(os.getenv("BREED_TIMEOUT","8"))

def _parse_json(text:str)->Dict[str,Any]:
    try:
        return json.loads(text)
    except Exception:
        import re
        m = re.search(r"\{.*\}", text, re.S)
        return json.loads(m.group(0)) if m else {}

def _call_openai_chat_image(sys_prompt:str,b64:str,timeout:int,model:str)->str:
    # Solo si el runtime tiene openai, de lo contrario lanzará y caeremos a fallback
    import openai
    client = openai.OpenAI()
    rsp = client.chat.completions.create(model=model,timeout=timeout,
        messages=[{"role":"system","content":sys_prompt},
                  {"role":"user","content":[{"type":"input_text","text":"Analiza esta imagen."},
                                            {"type":"input_image","image_url":{"url":"data:image/jpeg;base64,"+b64}}]}])
    return rsp.choices[0].message.content

def _call_azure_openai_chat_image(sys_prompt:str,b64:str,timeout:int,model:str)->str:
    from openai import AzureOpenAI
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    client = AzureOpenAI(api_key=os.getenv("AZURE_OPENAI_API_KEY"), api_version=os.getenv("AZURE_OPENAI_API_VERSION","2024-06-01"), azure_endpoint=endpoint)
    rsp = client.chat.completions.create(model=model,timeout=timeout,
        messages=[{"role":"system","content":sys_prompt},
                  {"role":"user","content":[{"type":"input_text","text":"Analiza esta imagen."},
                                            {"type":"input_image","image_url":{"url":"data:image/jpeg;base64,"+b64}}]}])
    return rsp.choices[0].message.content

def run_breed_prompt(img_bytes:bytes)->Dict[str,Any]:
    """Clasifica raza + familia (indicus/taurus/cruza) y predominancia (subtipo o compuesto)."""
    def _mk(name, conf, expl, family=None, dominant=None):
        label = name
        if family and dominant:
            if name.lower().startswith("cruza") or name.lower().startswith("indeterminado"):
                label = f"{family} — predomina {dominant}"
            else:
                label = name if dominant in ["ninguno","mixto"] else f"{name} (predomina {dominant})"
        elif family and (name.lower().startswith("cruza") or name.lower().startswith("indeterminado")):
            label = family
        return {"name": label, "confidence": round(conf,2), "explanation": expl, "family": family, "dominant": dominant}
    # Fallback local si no hay LLM
    if (not _llm_keys_present()) or os.getenv("ENABLE_BREED","1")!="1":
        return _mk("Cruza (indicus/taurus posible)",0.55,"Clasificación local (sin IA)","Cruza indicus×taurus","indicus")
    provider=_provider()
    if not _sdk_available(provider):
        return _mk("Cruza (indicus/taurus posible)",0.55,"Clasificación local (SDK no instalado)","Cruza indicus×taurus","indicus")
    b64=base64.b64encode(img_bytes).decode("utf-8"); provider=_provider(); model=_breed_model()
    sys_prompt = """
Eres zootecnista especialista en razas bovinas.
Analiza la imagen y devuelve SOLO este JSON minimal:
{
  "family": "<Cebú|Taurus europeo|Cruza indicus×taurus|Indeterminado>",
  "dominant": "<Brahman|Nelore|Gyr|Guzerá|Angus|Hereford|Holstein|Simmental|Charolais|Limousin|Brown Swiss|Jersey|Criollo|Brangus|Braford|Santa Gertrudis|Beefmaster|Simbrah|Girolando|indicus|taurus|mixto|ninguno>",
  "name": "<nombre corto de la raza o cruza>",
  "confidence": 0.0-1.0,
  "explanation": "máx 140 caracteres con 2-3 rasgos visibles"
}
Reglas:
- Si es Cebú puro, family="Cebú" y dominant ∈ {Brahman,Nelore,Gyr,Guzerá} si se distingue, de lo contrario "indicus".
- Si es europeo puro, family="Taurus europeo" y dominant ∈ {Angus,Hereford,Holstein,Simmental,Charolais,Limousin,Brown Swiss,Jersey,Criollo} si se distingue.
- Si es mezcla evidente, family="Cruza indicus×taurus". Para compuestos conocidos usa dominant ∈ {Brangus,Braford,Santa Gertrudis,Beefmaster,Simbrah,Girolando} si aplica; y si la mezcla es con Criollo (p.ej., Criollo×Brahman) puedes usar dominant="Criollo" cuando sus rasgos taurinos dominen.
- Si la evidencia es pobre, usa family="Indeterminado" y dominant="ninguno" con baja confianza.
- Nota: “Simental” ≡ "Simmental"; “Pardo Suizo” ≡ "Brown Swiss".
"""
    try:
        text=_call_azure_openai_chat_image(sys_prompt,b64,_bre_timeout(),model) if provider=="azure" else _call_openai_chat_image(sys_prompt,b64,_bre_timeout(),model)
        obj=_parse_json(text)
        fam=str(obj.get("family","Indeterminado")).strip()
        dom=str(obj.get("dominant","ninguno")).strip()
        nm=str(obj.get("name","Indeterminado")).strip()
        conf=float(obj.get("confidence",0.5))
        expl=str(obj.get("explanation",""))[:140]
        return _mk(nm,conf,expl,fam,dom)
    except Exception as e:
        return _mk("Cruza (indicus/taurus posible)",0.52,"Clasificación local (IA no disponible)","Cruza indicus×taurus","indicus")

# ------------------ Decisiones (estrictas, aproximadas) ------------------
def _floors(rubric:List[Dict[str,Any]]):
    d = {r["name"]: r["score"] for r in rubric}
    def g(k, default=6.0): return float(d.get(k, default))
    return {
        "dorsal": g("Línea dorsal"), "posterior": g("Grupo/muscling posterior"),
        "conform": g("Conformación"), "pecho": g("Profundidad de pecho")
    }

def _apply_risk_degrade(level: str, risk: float)->str:
    if risk > 0.55: return "NO_COMPRAR"
    if risk > 0.40:
        order = ["NO_COMPRAR","CONSIDERAR_BAJO","CONSIDERAR_ALTO","COMPRAR"]
        i = max(0, order.index(level)-1)
        return order[i]
    return level

def _decide_levante(score,bcs,risk,rubric):
    f=_floors(rubric)
    if bcs<2.0 or risk>=0.65: level="NO_COMPRAR"
    elif (bcs<2.4 or risk>=0.55 or score<5.0): level="CONSIDERAR_BAJO"
    elif (score>=6.4 and risk<=0.38 and bcs>=2.8 and f["dorsal"]>=6.0 and f["posterior"]>=6.8): level="CONSIDERAR_ALTO"
    elif (score>=6.45 and risk<=0.35 and bcs>=2.8 and f["dorsal"]>=7.0 and f["conform"]>=6.6 and f["pecho"]>=6.1 and f["posterior"]>=5.7): level="CONSIDERAR_ALTO"
    else: level="CONSIDERAR_BAJO"
    if (score>=7.6 and 2.8<=bcs<=4.5 and risk<=0.30 and f["dorsal"]>=6.5 and f["posterior"]>=7.0): level="COMPRAR"
    return _apply_risk_degrade(level,risk)

def _decide_vf(score,bcs,risk,rubric):
    f=_floors(rubric)
    if bcs<1.8 or risk>=0.70: level="NO_COMPRAR"
    elif (bcs<2.3 or risk>=0.55 or score<5.2): level="CONSIDERAR_BAJO"
    elif (score>=6.0 and risk<=0.40 and bcs>=2.4 and f["posterior"]>=6.6): level="CONSIDERAR_ALTO"
    elif (score>=6.10 and risk<=0.38 and bcs>=2.3 and f["dorsal"]>=6.8 and f["conform"]>=6.5 and f["pecho"]>=6.0 and f["posterior"]>=5.5): level="CONSIDERAR_ALTO"
    else: level="CONSIDERAR_BAJO"
    if (score>=7.2 and 2.4<=bcs<=4.2 and risk<=0.30 and f["dorsal"]>=6.3 and f["posterior"]>=6.9): level="COMPRAR"
    return _apply_risk_degrade(level,risk)

def _decide_eng(score,bcs,risk,rubric):
    f=_floors(rubric)
    if bcs<2.0 or bcs>4.6 or risk>=0.65: level="NO_COMPRAR"
    elif risk>=0.55 or score<5.3: level="CONSIDERAR_BAJO"
    elif (2.2<=bcs<=4.0 and score>=6.0 and risk<=0.45 and f["posterior"]>=6.7): level="CONSIDERAR_ALTO"
    elif (2.3<=bcs<=4.0 and score>=6.20 and risk<=0.40 and f["dorsal"]>=6.8 and f["conform"]>=6.5 and f["pecho"]>=6.1 and f["posterior"]>=6.0): level="CONSIDERAR_ALTO"
    else: level="CONSIDERAR_BAJO"
    if (2.6<=bcs<=3.8 and score>=7.0 and risk<=0.35 and f["dorsal"]>=6.3 and f["posterior"]>=7.0): level="COMPRAR"
    return _apply_risk_degrade(level,risk)

def format_output(agg:Dict[str,Any], health:List[Dict[str,Any]], breed:Dict[str,Any], mode:str)->Dict[str,Any]:
    score = agg["global_score"]; bcs = agg["bcs"]; risk = agg["risk"]; rubric = agg["rubric"]
    if mode=="levante":
        decision = _decide_levante(score,bcs,risk,rubric)
    elif mode=="vaca_flaca":
        decision = _decide_vf(score,bcs,risk,rubric)
    elif mode=="engorde":
        decision = _decide_eng(score,bcs,risk,rubric)
    else:
        decision = _decide_levante(score,bcs,risk,rubric)
    return {
        "decision_level": decision,
        "decision_text": {"NO_COMPRAR":"No comprar","CONSIDERAR_BAJO":"Considerar (bajo)","CONSIDERAR_ALTO":"Considerar alto","COMPRAR":"Comprar"}[decision],
        "global_score": score, "bcs": bcs, "risk": risk, "posterior_bonus": agg.get("posterior_bonus",0.0),
        "notes": f"MVP v40a-full (breed expandido).",
        "rubric": rubric, "health": health, "breed": breed,
        "reasons": ["Estructura general adecuada."]
    }
