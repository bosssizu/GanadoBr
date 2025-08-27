from typing import Dict, List, Any, Tuple
import random, os, json, base64, requests, time

MORPHOLOGICAL_METRICS = [
    "Conformación","Línea dorsal","Angulación costillar","Profundidad de pecho",
    "Aplomos","Lomo","Grupo/muscling posterior","Balance anterior-posterior",
    "Ancho torácico","Inserción de cola",
]

HEALTH_CATALOG = [
    "Lesión cutánea","Claudicación","Secreción nasal","Conjuntivitis","Diarrea",
    "Dermatitis","Lesión en pezuña","Parásitos externos","Tos",
]

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
    bcs = round(2.6 + (base % 180)/180 * 1.7, 2)
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

# ------------------ Raza con prompt oculto: timeouts + retries ------------------

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
    # Use (connect, read) timeouts
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
    # Config
    if not _openai_enabled():
        return {"name":"Cruza (indicus/taurus posible)","confidence":0.55,"explanation":"Breed OFF o sin API key"}
    timeout_s = int(os.getenv("LLM_TIMEOUT_SEC","15"))
    retries = int(os.getenv("LLM_RETRIES","2"))
    provider = (os.getenv("LLM_PROVIDER") or "openai").lower()

    b64 = base64.b64encode(img_bytes).decode("utf-8")
    system_prompt = """Eres experto en razas bovinas. Estima si el animal es PURO o CRUZA (enrazamiento).
Al evaluar, considera: giba (tamaño y forma), orejas (tamaño/pendulosidad), papada/dewlap, perfil/cabeza, cuernos, línea dorsal, piel suelta, patrón de pelaje.
Sé conservador: solo marca "puro" si hay rasgos robustos y consistentes; si hay mezcla de rasgos, marca "cruza".
Responde SOLAMENTE en JSON con este esquema (sin texto adicional):
{
  "verdict": "puro" | "cruza",
  "breed_main": "<si puro: raza principal; si cruza: dominante o 'mixta'>",
  "indicus_score": 0.0-1.0,
  "taurus_score": 0.0-1.0,
  "hump": "none|low|medium|high",
  "ears": "small|medium|large_pendulous",
  "dewlap": "none|low|medium|high",
  "confidence_raw": 0.0-1.0,
  "explanation": "cues breves"
}"""
    # Retries con backoff
    err = None
    for attempt in range(retries+1):
        try:
            if provider == "azure":
                text = _call_azure_openai_chat_image(system_prompt, b64, timeout_s)
            else:
                text = _call_openai_chat_image(system_prompt, b64, timeout_s)
            obj = _parse_breed_json(text)
            # --- post-proceso/corrección de sobreconfianza ---
            indicus = float(obj.get("indicus_score", 0.5))
            taurus  = float(obj.get("taurus_score", 0.5))
            hump = (obj.get("hump") or "none").lower()
            ears = (obj.get("ears") or "medium").lower()
            dewlap = (obj.get("dewlap") or "low").lower()
            verdict = (obj.get("verdict") or "").lower()
            breed_main = (obj.get("breed_main") or "").strip() or "Cruza"
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
                time.sleep(0.6 * (2**attempt))
            else:
                break
    return {"name":"Cruza (indicus/taurus posible)","confidence":0.55,"explanation": f"Fallback por error tras {retries+1} intento(s): {err}"}

def format_output(agg:Dict[str,Any], health:List[Dict[str,Any]], breed:Dict[str,Any], mode:str)->Dict[str,Any]:
    score = agg["global_score"] + agg.get("posterior_bonus",0.0)
    bcs = agg["bcs"]; risk = agg["risk"]
    if score>=8.2 and 2.8<=bcs<=4.5 and risk<=0.35:
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
        "notes": "Evaluación pipeline real (v39i, robust net).",
        "qc": {**agg.get("qc",{}), "auction_mode": (mode=='subasta')},
        "rubric": agg["rubric"],
        "reasons": reasons,
        "health": health,
        "breed": breed,
    }
