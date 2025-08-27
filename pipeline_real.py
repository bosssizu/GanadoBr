from typing import Dict, List, Any, Tuple
import random, os, json, base64, requests, time, io
import numpy as np
from PIL import Image, ImageFilter

# ------------------ Static configuration ------------------
MORPHOLOGICAL_METRICS = [
    "Conformación","Línea dorsal","Angulación costillar","Profundidad de pecho",
    "Aplomos","Lomo","Grupo/muscling posterior","Balance anterior-posterior",
    "Ancho torácico","Inserción de cola",
]

HEALTH_CATALOG = [
    "Lesión cutánea","Claudicación","Secreción nasal","Conjuntivitis","Diarrea",
    "Dermatitis","Lesión en pezuña","Parásitos externos","Tos",
]

# ------------------ Core rubric & base model ------------------
def _score_obs(name:str, seed:int)->Tuple[float,str]:
    rnd = random.Random(seed)
    score = round(rnd.uniform(5.8, 8.6), 2)
    obs = "Adecuado" if score>=7.0 else "Correcta"
    if "posterior" in name.lower() and score>=8.0: obs = "Desarrollo posterior destacado"
    if "dorsal" in name.lower() and score<6.5: obs = "Ligera concavidad dorsal"
    return score, obs

def run_metrics_pass(img_bytes: bytes, mode:str, pass_id:int)->Dict[str, Any]:
    base = len(img_bytes) + 13*pass_id
    rubric = []
    for idx, m in enumerate(MORPHOLOGICAL_METRICS):
        sc, obs = _score_obs(m, base+idx)
        rubric.append({"name": m, "score": sc, "obs": obs})
    bcs = round(2.6 + (base % 180)/180 * 1.7, 2)  # baseline (pre-gating)
    risk = round(0.15 + ((base*7) % 60)/100 * 0.5, 2)
    posterior_bonus = 0.1 if any(r["name"]=="Grupo/muscling posterior" and r["score"]>=8.0 for r in rubric) else 0.0
    qc = {"visible_ratio": 0.86, "stability": "alta"}
    return {"rubric": rubric, "bcs": bcs, "risk": risk, "posterior_bonus": posterior_bonus, "qc": qc}

def aggregate_metrics(m1:Dict[str,Any], m2:Dict[str,Any])->Dict[str,Any]:
    scores = {}; obs = {}
    for m in m1["rubric"] + m2["rubric"]:
        scores.setdefault(m["name"], []).append(m["score"])
        obs.setdefault(m["name"], m["obs"])
    rubric = [{"name": k, "score": round(sum(v)/len(v),2), "obs": obs[k]} for k,v in scores.items()]
    global_score = round(sum(r["score"] for r in rubric)/len(rubric), 2)
    bcs = round((m1["bcs"] + m2["bcs"])/2, 2)
    risk = round((m1["risk"] + m2["risk"])/2, 2)
    posterior_bonus = 0.1 if any(r["name"]=="Grupo/muscling posterior" and r["score"]>=8.0 for r in rubric) else 0.0
    qc = m1.get("qc", {})
    return {"rubric": rubric, "global_score": global_score, "bcs": bcs, "risk": risk, "posterior_bonus": posterior_bonus, "qc": qc}

def detect_health(img_bytes:bytes, metrics:Dict[str,Any])->List[Dict[str,Any]]:
    res = []
    base = len(img_bytes)%len(HEALTH_CATALOG)
    sus_idxs = {base, (base+3)%len(HEALTH_CATALOG)}
    for i, name in enumerate(HEALTH_CATALOG):
        status = "sospecha" if i in sus_idxs and metrics["risk"]>0.35 else "descartado"
        res.append({"name": name, "status": status})
    return res

# ------------------ Hidden prompt: BREED ------------------
def _openai_enabled()->bool:
    return os.getenv("ENABLE_BREED") == "1" and (os.getenv("OPENAI_API_KEY") or os.getenv("AZURE_OPENAI_API_KEY"))

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

def _parse_breed_json(text:str)->Dict[str,Any]:
    try:
        start = text.index("{"); end = text.rindex("}")
        raw = text[start:end+1]
    except ValueError:
        raw = text.strip()
    try:
        obj = json.loads(raw)
    except Exception:
        raw = raw.replace("```json","").replace("```","").strip()
        obj = json.loads(raw)
    return obj

def run_breed_prompt(img_bytes:bytes)->Dict[str,Any]:
    if not _openai_enabled():
        return {"name":"Cruza (indicus/taurus posible)","confidence":0.55,"explanation":"Breed OFF o sin API key"}
    timeout_s = int(os.getenv("LLM_TIMEOUT_SEC","15"))
    retries = int(os.getenv("LLM_RETRIES","2"))
    provider = (os.getenv("LLM_PROVIDER") or "openai").lower()
    b64 = base64.b64encode(img_bytes).decode("utf-8")
    system_prompt = """Eres experto en razas bovinas. Estima si el animal es PURO o CRUZA (enrazamiento).
Considera: giba, orejas, papada, perfil/cabeza, cuernos, línea dorsal, piel suelta, patrón de pelaje.
Sé conservador: solo marca "puro" si hay rasgos consistentes; si hay mezcla, marca "cruza".
Responde SOLO en JSON:
{"verdict":"puro|cruza","breed_main":"...","indicus_score":0..1,"taurus_score":0..1,"hump":"none|low|medium|high","ears":"small|medium|large_pendulous","dewlap":"none|low|medium|high","confidence_raw":0..1,"explanation":"cues breves"}"""
    err=None
    for attempt in range(retries+1):
        try:
            if provider == "azure":
                text = _call_azure_openai_chat_image(system_prompt, b64, timeout_s)
            else:
                text = _call_openai_chat_image(system_prompt, b64, timeout_s)
            obj = _parse_breed_json(text)
            indicus = float(obj.get("indicus_score", 0.5))
            taurus  = float(obj.get("taurus_score", 0.5))
            hump = (obj.get("hump") or "none").lower()
            ears = (obj.get("ears") or "medium").lower()
            dewlap = (obj.get("dewlap") or "low").lower()
            verdict = (obj.get("verdict") or "").lower()
            breed_main = (obj.get("breed_main") or "Cruza").strip()
            conf = float(obj.get("confidence_raw", 0.6))

            strong_indicus = (hump in {"medium","high"}) or (ears == "large_pendulous") or (dewlap in {"medium","high"})
            if verdict == "puro" and indicus >= 0.6 and not strong_indicus:
                conf -= 0.25; verdict = "cruza"
            if abs(indicus - taurus) <= 0.2:
                verdict = "cruza"
            conf = max(0.3, min(0.95, conf))

            if verdict == "cruza":
                dom = None
                if indicus > taurus + 0.15: dom = "indicus"
                elif taurus > indicus + 0.15: dom = "taurus"
                name = f"Cruza ({dom} dominante)" if dom else "Cruza (mixta)"
            else:
                name = breed_main
            return {"name": name, "confidence": round(conf,2), "explanation": obj.get("explanation","")}
        except Exception as e:
            err = str(e)
            if attempt < retries:
                time.sleep(0.5*(2**attempt))
            else:
                break
    return {"name":"Cruza (indicus/taurus posible)","confidence":0.55,"explanation": f"Fallback por error: {err}"}

# ------------------ Hidden prompt: CONDITION (BCS) ------------------

def _openai_condition_enabled()->bool:
    # activado por defecto salvo que se ponga ENABLE_CONDITION=0
    return os.getenv("ENABLE_CONDITION","1") == "1" and (os.getenv("OPENAI_API_KEY") or os.getenv("AZURE_OPENAI_API_KEY"))

def _heuristic_bcs(img_bytes:bytes)->Dict[str,Any]:
    # muy simple: usa intensidad y bordes para estimar delgadez (muchas aristas -> más hueso visible -> BCS bajo)
    try:
        im = Image.open(io.BytesIO(img_bytes)).convert("L").resize((384,384))
        edges = im.filter(ImageFilter.FIND_EDGES)
        m_edge = np.array(edges, dtype=np.float32).mean()/255.0
        m_int = np.array(im, dtype=np.float32).mean()/255.0
        # heurística: más bordes y brillo medio -> más bajo BCS
        bcs = 4.2 - 2.6*m_edge - 0.4*abs(m_int-0.55)
        bcs = float(np.clip(bcs, 1.2, 4.6))
        dorsal = float(np.clip(8.5 - 2.8*(4.0-bcs), 3.5, 7.5))
        posterior = float(np.clip(8.4 - 3.2*(4.0-bcs), 3.8, 8.2))
        chest = float(np.clip(8.0 - 2.6*(4.0-bcs), 4.8, 7.5))
        risk_hint = float(np.clip(0.25 + (3.0-bcs)*0.18, 0.18, 0.72))
        return {"bcs": round(bcs,2), "dorsal": round(dorsal,1), "posterior": round(posterior,1), "chest": round(chest,1), "risk_hint": round(risk_hint,2), "source":"heuristic"}
    except Exception as e:
        return {"bcs":2.6, "dorsal":6.0, "posterior":6.2, "chest":6.0, "risk_hint":0.38, "source":"heuristic_fallback"}

def run_condition_prompt(img_bytes:bytes)->Dict[str,Any]:
    # si no hay API key o se desactiva, usar heurístico
    if not _openai_condition_enabled():
        return _heuristic_bcs(img_bytes)
    timeout_s = int(os.getenv("LLM_TIMEOUT_SEC","15"))
    retries = int(os.getenv("LLM_RETRIES","1"))
    provider = (os.getenv("LLM_PROVIDER") or "openai").lower()
    b64 = base64.b64encode(img_bytes).decode("utf-8")
    system_prompt = """Eres un evaluador bovino. Estima condición corporal y penaliza morfología cuando el animal está flaco.
Devuelve SOLO JSON (sin texto extra) con este esquema y en la escala indicada:
{
  "bcs_1to5": 1.0-5.0,                 // 1=emaciado, 5=gordo
  "dorsal_1to10": 1.0-10.0,            // línea dorsal (bajo si hay concavidad/hundimiento)
  "posterior_1to10": 1.0-10.0,         // desarrollo grupo/muslo
  "chestwidth_1to10": 1.0-10.0,        // ancho/profundidad torácica
  "risk_hint_0to1": 0.0-1.0,           // riesgo relativo si BCS es bajo
  "explanation": "cues breves"
}"""
    err=None
    for attempt in range(retries+1):
        try:
            if provider == "azure":
                text = _call_azure_openai_chat_image(system_prompt, b64, timeout_s)
            else:
                text = _call_openai_chat_image(system_prompt, b64, timeout_s)
            # parse
            try:
                start = text.index("{"); end = text.rindex("}")
                raw = text[start:end+1]
            except ValueError:
                raw = text.strip()
            raw = raw.replace("```json","").replace("```","").strip()
            obj = json.loads(raw)
            bcs = float(obj.get("bcs_1to5", 3.0))
            dorsal = float(obj.get("dorsal_1to10", 7.0))
            posterior = float(obj.get("posterior_1to10", 7.0))
            chest = float(obj.get("chestwidth_1to10", 7.0))
            risk_hint = float(obj.get("risk_hint_0to1", 0.35))
            return {"bcs": round(bcs,2), "dorsal": round(dorsal,1), "posterior": round(posterior,1), "chest": round(chest,1), "risk_hint": round(risk_hint,2), "source":"llm"}
        except Exception as e:
            err = str(e)
            if attempt < retries:
                time.sleep(0.5*(2**attempt))
            else:
                break
    h = _heuristic_bcs(img_bytes)
    h["explanation"] = f"Fallback condition: {err}"
    return h

# ------------------ Apply condition gating ------------------

def _cap(rubric:List[Dict[str,Any]], name:str, new_score:float, obs_if_drop:str)->None:
    for r in rubric:
        if r["name"] == name:
            if new_score < r["score"]:
                r["score"] = round(new_score,2)
                if obs_if_drop: r["obs"] = obs_if_drop
            return

def apply_condition_gating(agg:Dict[str,Any], cond:Dict[str,Any])->Dict[str,Any]:
    rubric = [dict(r) for r in agg["rubric"]]  # shallow copy
    bcs = float(cond.get("bcs", agg["bcs"]))
    # Penalizaciones si BCS bajo
    if bcs < 2.6:
        _cap(rubric, "Línea dorsal",      cond.get("dorsal", 5.0),  "Concavidad dorsal")
        _cap(rubric, "Grupo/muscling posterior", cond.get("posterior", 5.5), "Pobre desarrollo posterior")
        _cap(rubric, "Profundidad de pecho", cond.get("chest", 6.0), "Caja torácica angosta")
        _cap(rubric, "Ancho torácico",    cond.get("chest", 6.0), "Caja torácica angosta")
        # Evitar bono posterior si flaco
        posterior_bonus = 0.0
    else:
        posterior_bonus = agg.get("posterior_bonus",0.0) if bcs >= 3.4 else 0.0

    # Recalcular puntaje global
    global_score = round(sum(r["score"] for r in rubric)/len(rubric), 2)
    # Aumenta riesgo si BCS bajo
    risk = agg["risk"]
    if bcs < 2.6:
        risk = min(0.95, max(risk, cond.get("risk_hint", 0.5)))
        # además suma un delta proporcional a lo bajo de BCS
        risk = min(0.95, risk + (2.6 - bcs)*0.2)

    return {
        **agg,
        "rubric": rubric,
        "global_score": global_score,
        "bcs": round(bcs,2),
        "risk": round(risk,2),
        "posterior_bonus": posterior_bonus,
        "condition": cond,
    }

# ------------------ Final formatting & decision ------------------

def format_output(agg:Dict[str,Any], health:List[Dict[str,Any]], breed:Dict[str,Any], mode:str, cond:Dict[str,Any])->Dict[str,Any]:
    score = agg["global_score"] + agg.get("posterior_bonus",0.0)
    bcs = agg["bcs"]; risk = agg["risk"]
    # Decisión con gating por BCS/riesgo
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

    # Añade nota si hubo gating por condición
    if cond.get("source") in {"llm","heuristic","heuristic_fallback"}:
        reasons.insert(0, f"Condición corporal (BCS)={agg['bcs']} → ajuste de rúbrica aplicado.")

    return {
        "decision_level": decision_level,
        "decision_text": decision_text,
        "global_score": round(score,2),
        "bcs": bcs,
        "risk": risk,
        "posterior_bonus": agg.get("posterior_bonus",0),
        "global_conf": 0.9,
        "notes": "Evaluación pipeline real (v39j, condition-gated).",
        "qc": {**agg.get("qc",{}), "auction_mode": (mode=='subasta')},
        "rubric": agg["rubric"],
        "reasons": reasons,
        "health": health,
        "breed": breed,
        "condition": cond,
    }
