"""
GanadoBravo — pipeline_real.py (v38)

Coloca aquí TU lógica real. Estas funciones serán llamadas por main.py:
- run_metrics_pass(img, mode, pass_id)
- aggregate_metrics(m1, m2)
- detect_health(img, metrics)
- run_breed_prompt(img)
- format_output(metrics, health, breed, mode)
"""
from typing import Any, Dict

# Ejemplo de estructura intermedia esperada (ajusta a tu implementación):
# m = { "scores": {...}, "bcs": 3.5, "risk": 0.2, "posterior_bonus": 0.1, "rubric": [...],
#       "global_score": 7.4, "global_conf": 0.93, "reasons": ["..."] }

def run_metrics_pass(img, mode: str, pass_id: int) -> Dict[str, Any]:
    # TODO: Reemplaza con TU evaluación real (pasada 1/2).
    # No hagas I/O de red aquí salvo que sea imprescindible.
    raise NotImplementedError("Implementa run_metrics_pass")

def aggregate_metrics(m1: Dict[str, Any], m2: Dict[str, Any]) -> Dict[str, Any]:
    # TODO: Combina/valida m1 y m2 (promedios/consistencia).
    raise NotImplementedError("Implementa aggregate_metrics")

def detect_health(img, metrics: Dict[str, Any]):
    # TODO: Heurísticas de salud (sin mostrar configs/oval).
    # Devuelve lista de dicts: [{"name":"Lesión cutánea", "severity":"descartado"}, ...]
    raise NotImplementedError("Implementa detect_health")

def run_breed_prompt(img):
    # TODO: Prompt oculto de raza (heurístico/LLM/modelo), resalta criollo/entrecruzamiento.
    # Devuelve dict: {"name":"Criollo (...)", "confidence":0.58, "explanation":"..."}
    raise NotImplementedError("Implementa run_breed_prompt")

def format_output(metrics: Dict[str, Any], health, breed, mode: str):
    # TODO: Construye el objeto final que la UI espera.
    # Campos mínimos:
    # - decision_level: "NO_COMPRAR" | "CONSIDERAR_BAJO" | "CONSIDERAR_ALTO" | "COMPRAR"
    # - decision_text:  "No comprar" | "Considerar bajo" | "Considerar alto" | "Comprar"
    # - global_score, bcs, risk, posterior_bonus, global_conf, notes
    # - qc.visible_ratio, qc.stability (si aplica)
    # - rubric: [{"name":..., "score":..., "obs":...}, ...]
    # - reasons: ["...", ...]
    # - health: lista (ver arriba)
    # - breed: dict (ver arriba)
    raise NotImplementedError("Implementa format_output")


# ======================= AI-FIRST FULL EVALUATION =======================
import json as _json, base64 as _b64, os as _os
from typing import Any as _Any, Dict as _Dict, List as _List

def _get_ai_provider():
    if _os.getenv("AZURE_OPENAI_API_KEY") and _os.getenv("AZURE_OPENAI_ENDPOINT"):
        return "azure"
    return "openai"

def _openai_headers():
    return {"Authorization": f"Bearer {_os.getenv('OPENAI_API_KEY','')}", "Content-Type": "application/json"}

def _azure_headers():
    return {"api-key": _os.getenv("AZURE_OPENAI_API_KEY",""), "Content-Type": "application/json"}

def _img_to_b64(img_bytes: bytes) -> str:
    return "data:image/jpeg;base64," + _b64.b64encode(img_bytes).decode("utf-8")

def _ai_system_prompt(mode: str) -> str:
    return f"""Eres un evaluador zootecnista experto. Evalúa bovinos en la foto para el objetivo: '{mode}'.
Devuelve SOLO un JSON con este esquema (sin texto adicional):
{{
  "decision_level": "NO_COMPRAR|CONSIDERAR_BAJO|CONSIDERAR_ALTO|COMPRAR",
  "decision_text": "texto corto",
  "global_score": number,
  "bcs": number,
  "risk": number,
  "rubric": [
    {{"name":"Conformación","score":number,"obs":"..."}},
    {{"name":"Línea dorsal","score":number,"obs":"..."}},
    {{"name":"Angulación costillar","score":number,"obs":"..."}},
    {{"name":"Profundidad de pecho","score":number,"obs":"..."}},
    {{"name":"Aplomos","score":number,"obs":"..."}},
    {{"name":"Lomo","score":number,"obs":"..."}},
    {{"name":"Grupo/muscling posterior","score":number,"obs":"..."}},
    {{"name":"Balance anterior-posterior","score":number,"obs":"..."}},
    {{"name":"Ancho torácico","score":number,"obs":"..."}},
    {{"name":"Inserción de cola","score":number,"obs":"..."}}
  ],
  "health":[
    {{"name":"Lesión cutánea","status":"descartado|sospecha"}},
    {{"name":"Claudicación","status":"descartado|sospecha"}},
    {{"name":"Secreción nasal","status":"descartado|sospecha"}},
    {{"name":"Conjuntivitis","status":"descartado|sospecha"}},
    {{"name":"Diarrea","status":"descartado|sospecha"}},
    {{"name":"Dermatitis","status":"descartado|sospecha"}},
    {{"name":"Lesión en pezuña","status":"descartado|sospecha"}},
    {{"name":"Parásitos externos","status":"descartado|sospecha"}},
    {{"name":"Tos","status":"descartado|sospecha"}}
  ],
  "breed": {{
    "name": "Brahman|Cebú|Angus|Brangus|Criollo|Cruza indicus×taurus|…",
    "confidence": number,
    "explanation": "1-2 frases",
    "family": "Bos indicus|Bos taurus|Cruza",
    "dominant": "indicus|taurus|ninguno"
  }},
  "reasons": ["bullet 1","bullet 2"]
}}"""

def _ai_user_payload(img_b64: str):
    return [{"type":"text","text":"Evalúa estrictamente y devuelve SOLO el JSON pedido."},
            {"type":"image_url","image_url":{"url": img_b64}}]

def _call_openai_vision(img_bytes: bytes, mode: str, model: str, timeout: int = 14) -> _Dict[str,_Any]:
    provider = _get_ai_provider()
    img_b64 = _img_to_b64(img_bytes)
    system = _ai_system_prompt(mode)
    messages = [{"role":"system","content":system},{"role":"user","content": _ai_user_payload(img_b64)}]

    import requests
    if provider == "openai":
        api = "https://api.openai.com/v1/chat/completions"
        body = {"model": model or "gpt-4o-mini", "messages": messages, "temperature": 0.2}
        r = requests.post(api, headers=_openai_headers(), json=body, timeout=timeout)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
    else:
        dep = _os.getenv("AZURE_OPENAI_DEPLOYMENT","")
        endpoint = _os.getenv("AZURE_OPENAI_ENDPOINT","").rstrip("/")
        api = f"{endpoint}/openai/deployments/{dep}/chat/completions?api-version={_os.getenv('AZURE_OPENAI_API_VERSION','2024-06-01')}"
        body = {"messages": messages, "temperature": 0.2}
        r = requests.post(api, headers=_azure_headers(), json=body, timeout=timeout)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]

    import re
    m = re.search(r"\\{.*\\}", content, re.S)
    if not m:
        raise ValueError("AI did not return JSON")
    data = _json.loads(m.group(0))
    data["decision_level"] = str(data.get("decision_level","")).upper().replace(" ", "_")
    return data

def ai_first_full_eval(img_bytes: bytes, mode: str, model: str = None, timeout: int = None) -> _Dict[str,_Any]:
    mdl = model or _os.getenv("OPENAI_MODEL", _os.getenv("BREED_MODEL","gpt-4o-mini"))
    tmo = timeout or int(_os.getenv("EVAL_TIMEOUT","14"))
    return _call_openai_vision(img_bytes, mode, mdl, timeout=tmo)
# ===================== END AI-FIRST FULL EVALUATION =====================
