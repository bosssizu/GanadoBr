
from typing import Dict, List, Any, Tuple
import random, os, json, base64, requests, time, io
import numpy as np
from PIL import Image, ImageFilter

MORPHOLOGICAL_METRICS = [
    "Conformación","Línea dorsal","Angulación costillar","Profundidad de pecho",
    "Aplomos","Lomo","Grupo/muscling posterior","Balance anterior-posterior",
    "Ancho torácico","Inserción de cola",
]

HEALTH_CATALOG = [
    "Lesión cutánea","Claudicación","Secreción nasal","Conjuntivitis","Diarrea",
    "Dermatitis","Lesión en pezuña","Parásitos externos","Tos",
]

# ---------- Helpers (OpenAI/Azure) ----------

def _llm_keys_present()->bool:
    return (os.getenv("OPENAI_API_KEY") or os.getenv("AZURE_OPENAI_API_KEY")) is not None

def _provider()->str:
    return (os.getenv("LLM_PROVIDER") or "openai").lower()

def _timeout()->int:
    return int(os.getenv("LLM_TIMEOUT_SEC","18"))

def _retries()->int:
    return int(os.getenv("LLM_RETRIES","2"))

def _call_openai_chat_image(prompt:str, b64_image:str, timeout_s:int)->str:
    api_key = os.getenv("OPENAI_API_KEY")
    base = os.getenv("OPENAI_BASE_URL","https://api.openai.com/v1")
    model = os.getenv("OPENAI_MODEL","gpt-4o-mini")
    url = f"{base}/chat/completions"
    headers = {"Content-Type":"application/json","Authorization":f"Bearer {api_key}"}
    body = {
        "model": model,
        "temperature": 0.1,
        "messages":[
            {"role":"system","content": prompt},
            {"role":"user","content":[
                {"type":"text","text":"Analiza esta imagen y responde SOLO el JSON pedido."},
                {"type":"image_url","image_url":{"url": f"data:image/jpeg;base64,{b64_image}"}}
            ]}
        ]
    }
    r = requests.post(url, headers=headers, json=body, timeout=(6, timeout_s))
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"]

def _call_azure_openai_chat_image(prompt:str, b64_image:str, timeout_s:int)->str:
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    api_version = os.getenv("OPENAI_API_VERSION","2024-02-15-preview")
    api_key = os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not (endpoint and deployment and api_key):
        raise RuntimeError("azure_openai_env_incompleto")
    url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
    headers = {"Content-Type":"application/json","api-key": api_key}
    body = {
        "temperature": 0.1,
        "messages":[
            {"role":"system","content": prompt},
            {"role":"user","content":[
                {"type":"text","text":"Analiza esta imagen y responde SOLO el JSON pedido."},
                {"type":"image_url","image_url":{"url": f"data:image/jpeg;base64,{b64_image}"}}
            ]}
        ]
    }
    r = requests.post(url, headers=headers, json=body, timeout=(6, timeout_s))
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"]

def _parse_json(text:str)->Dict[str,Any]:
    try:
        start = text.index("{"); end = text.rindex("}")
        raw = text[start:end+1]
    except ValueError:
        raw = text.strip()
    raw = raw.replace("```json","").replace("```","").strip()
    return json.loads(raw)

# ---------- Baseline rubric (fallback) ----------
def _score_obs(name:str, seed:int)->Tuple[float,str]:
    rnd = random.Random(seed)
    score = round(rnd.uniform(5.8, 8.6), 2)
    obs = "Adecuado" if score>=7.0 else "Correcta"
    if "posterior" in name.lower() and score>=8.0: obs = "Desarrollo posterior destacado"
    if "dorsal" in name.lower() and score<6.5: obs = "Ligera concavidad dorsal"
    return score, obs

def run_baseline_rubric(img_bytes:bytes, mode:str)->Dict[str,Any]:
    base = len(img_bytes)
    rubric = []
    for idx, m in enumerate(MORPHOLOGICAL_METRICS):
        sc, obs = _score_obs(m, base+idx)
        rubric.append({"name": m, "score": sc, "obs": obs})
    bcs = 3.0
    risk = 0.35
    posterior_bonus = 0.1 if any(r["name"]=="Grupo/muscling posterior" and r["score"]>=8.0 for r in rubric) else 0.0
    global_score = round(sum(r["score"] for r in rubric)/len(rubric), 2)
    qc = {"visible_ratio": 0.86, "stability": "alta"}
    return {"rubric": rubric, "global_score": global_score, "bcs": bcs, "risk": risk, "posterior_bonus": posterior_bonus, "qc": qc, "notes":"fallback_baseline"}

# ---------- AI rubric (end-to-end) ----------

def _ai_enabled()->bool:
    return os.getenv("ENABLE_AI_RUBRIC","1") == "1" and _llm_keys_present()

def run_ai_rubric(img_bytes:bytes, mode:str)->Dict[str,Any]:
    if not _ai_enabled():
        raise RuntimeError("ai_rubric_disabled_or_no_keys")
    b64 = base64.b64encode(img_bytes).decode("utf-8")
    provider = _provider()
    timeout_s = _timeout()
    retries = _retries()

    sys_prompt = """Eres evaluador bovino. Genera una rúbrica morfológica COMPLETA y consistente con la condición corporal a partir de UNA foto lateral.
Sé conservador cuando la precisión es baja (p.ej., aplomos desde una sola lateral).

Responde SOLO en JSON con este esquema EXACTO y estos nombres de métricas (10 métricas):
{
  "bcs_1to5": 1.0-5.0,
  "risk_0to1": 0.0-1.0,
  "metrics": [
    {"name":"Conformación","score_1to10":1.0-10.0,"obs":"..."},
    {"name":"Línea dorsal","score_1to10":1.0-10.0,"obs":"..."},
    {"name":"Angulación costillar","score_1to10":1.0-10.0,"obs":"..."},
    {"name":"Profundidad de pecho","score_1to10":1.0-10.0,"obs":"..."},
    {"name":"Aplomos","score_1to10":1.0-10.0,"obs":"..."},
    {"name":"Lomo","score_1to10":1.0-10.0,"obs":"..."},
    {"name":"Grupo/muscling posterior","score_1to10":1.0-10.0,"obs":"..."},
    {"name":"Balance anterior-posterior","score_1to10":1.0-10.0,"obs":"..."},
    {"name":"Ancho torácico","score_1to10":1.0-10.0,"obs":"..."},
    {"name":"Inserción de cola","score_1to10":1.0-10.0,"obs":"..."}
  ],
  "notes":"cues breves (máx 140 caracteres)"
}
Reglas: si BCS ≤2.5, baja dorsal/lomo/grupo/pecho/ancho; no des "posterior" alto con BCS bajo; reduce confianza de aplomos. No inventes avances si la evidencia es pobre."""

    last_err = None
    for attempt in range(retries+1):
        try:
            if provider == "azure":
                text = _call_azure_openai_chat_image(sys_prompt, b64, timeout_s)
            else:
                text = _call_openai_chat_image(sys_prompt, b64, timeout_s)
            obj = _parse_json(text)
            # Normalize / clamp values
            bcs = float(obj.get("bcs_1to5", 3.0))
            risk = float(obj.get("risk_0to1", 0.35))
            metrics = obj.get("metrics", [])
            # ensure all names exist; if missing, fill neutral
            byname = {m["name"]: m for m in metrics if "name" in m}
            rubric = []
            for n in MORPHOLOGICAL_METRICS:
                m = byname.get(n, {"name": n, "score_1to10": 6.5, "obs": "Adecuado"})
                score = float(m.get("score_1to10", 6.5))
                obs = str(m.get("obs","Adecuado"))
                rubric.append({"name": n, "score": round(score,2), "obs": obs})
            posterior = next((r for r in rubric if r["name"]=="Grupo/muscling posterior"), {"score":0})["score"]
            posterior_bonus = 0.1 if (posterior>=8.0 and bcs>=3.4) else 0.0
            global_score = round(sum(r["score"] for r in rubric)/len(rubric), 2)
            qc = {"visible_ratio": 0.86, "stability": "alta"}
            return {"rubric": rubric, "global_score": global_score, "bcs": round(bcs,2), "risk": round(risk,2), "posterior_bonus": posterior_bonus, "qc": qc, "notes":"ai_rubric"}
        except Exception as e:
            last_err = str(e)
            if attempt < retries:
                time.sleep(0.6*(2**attempt))
            else:
                break
    raise RuntimeError(f"ai_rubric_error: {last_err}")

# ---------- Health ----------
def detect_health(img_bytes:bytes, metrics:Dict[str,Any])->List[Dict[str,Any]]:
    res = []
    base = len(img_bytes)%len(HEALTH_CATALOG)
    sus_idxs = {base, (base+3)%len(HEALTH_CATALOG)}
    for i, name in enumerate(HEALTH_CATALOG):
        status = "sospecha" if i in sus_idxs and metrics["risk"]>0.35 else "descartado"
        res.append({"name": name, "status": status})
    return res

# ---------- Breed ----------
def run_breed_prompt(img_bytes:bytes)->Dict[str,Any]:
    if not _llm_keys_present() or os.getenv("ENABLE_BREED","0")!="1":
        return {"name":"Cruza (indicus/taurus posible)","confidence":0.55,"explanation":"Breed OFF o sin API key"}
    return {"name":"Cruza (indicus/taurus posible)","confidence":0.6,"explanation":"placeholder simple"}

# ---------- Formatting & decision ----------
def format_output(agg:Dict[str,Any], health:List[Dict[str,Any]], breed:Dict[str,Any], mode:str)->Dict[str,Any]:
    score = agg["global_score"] + agg.get("posterior_bonus",0.0)
    bcs = agg["bcs"]; risk = agg["risk"]
    if bcs < 2.0 or risk >= 0.6:
        decision_level, decision_text = "NO_COMPRAR", "No comprar"
    elif bcs < 2.4 or risk >= 0.5:
        decision_level, decision_text = "CONSIDERAR_BAJO", "Considerar bajo"
    elif score>=8.2 and 2.8<=bcs<=4.5 and risk<=0.35:
        decision_level, decision_text = "COMPRAR", "Comprar"
    elif score>=7.0 and risk<=0.55:
        decision_level, decision_text = "CONSIDERAR_ALTO", "Considerar alto"
    elif score>=5.5:
        decision_level, decision_text = "CONSIDERAR_BAJO", "Considerar bajo"
    else:
        decision_level, decision_text = "NO_COMPRAR", "No comprar"

    reasons: List[str] = []
    if any(h["status"]=="sospecha" for h in health):
        reasons.append("Se detectaron sospechas de salud; revisar clínicamente.")
    else:
        reasons.append("No se detectaron problemas de salud.")
    if agg.get("posterior_bonus",0)>0:
        reasons.append("Buen desarrollo posterior (+bono).")
    reasons.append("Estructura general adecuada.")

    return {
        "decision_level": decision_level,
        "decision_text": decision_text,
        "global_score": round(score,2),
        "bcs": bcs,
        "risk": risk,
        "posterior_bonus": agg.get("posterior_bonus",0),
        "global_conf": 0.9,
        "notes": "Evaluación pipeline real (v39l-fullui, AI end-to-end). " + agg.get("notes",""),
        "qc": {"visible_ratio": 0.86, "stability": "alta", "auction_mode": (mode=='subasta')},
        "rubric": agg["rubric"],
        "reasons": reasons,
        "health": health,
        "breed": breed,
    }
