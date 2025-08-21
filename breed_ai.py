
from typing import Dict, Any, Optional
import base64, os, io
from PIL import Image

# Optional OpenAI client (v1)
try:
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore

# -------- System prompt (hidden) --------
SYSTEM_PROMPT = """
Eres un evaluador de raza EN FOTOS LATERALES de bovinos. Usa solo evidencia visible.
Objetivo: inferir enrazamiento y raza probable.
Reglas:
- Si hay señales de cebú (oreja larga caída, papada colgante, giba) -> ENRAZADO (Brahman o mix).
- Si NO hay señales de cebú, intenta taurino probable (Angus/Hereford/Charolais/Holstein/etc) o 'Criollo/Mix' si es ambiguo.
- No inventes; cuando no haya evidencia suficiente, devuelve 'Criollo/Mix' con confianza baja.
- Devuelve SOLO JSON válido con campos:
{
  "label": "Brahman/Mix | Angus | Hereford | Charolais | Holstein | Criollo/Mix",
  "class": "ENRAZADO | TAURINO | LECHERO | CRIOLLO",
  "conf": 0.0-1.0,
  "reason": "máx 180 caracteres, describe señales: oreja/papada/giba, patrón de pelaje, color, cara blanca, etc."
}
"""

USER_PROMPT = "Evalúa la raza probable del bovino en la imagen siguiendo las reglas. No uses texto externo. Responde solo JSON."

def _img_to_b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=90)
    return base64.b64encode(buf.getvalue()).decode("ascii")

def _call_openai(img: Image.Image, model: str = "gpt-4o-mini") -> Optional[Dict[str, Any]]:
    if OpenAI is None or os.getenv("OPENAI_API_KEY") is None:
        return None
    client = OpenAI()
    b64 = _img_to_b64(img)
    msg = client.chat.completions.create(
        model=model,
        temperature=0.0,
        messages=[
            {"role":"system","content":SYSTEM_PROMPT},
            {"role":"user","content":[
                {"type":"text","text":USER_PROMPT},
                {"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{b64}"}},
            ]}
        ],
        response_format={"type":"json_object"},
        timeout=20,
    )
    try:
        import json as _json
        data = _json.loads(msg.choices[0].message.content or "{}")
        # basic validation
        if not isinstance(data, dict): return None
        label = str(data.get("label","Criollo/Mix"))[:40]
        clazz = str(data.get("class","CRIOLLO"))[:16]
        conf = float(data.get("conf", 0.5))
        reason = str(data.get("reason",""))[:200]
        return {"label":label, "class":clazz, "conf":conf, "reason":reason, "source":"ai"}
    except Exception:
        return None

# --------- Stub provider (dev/offline): uses existing heuristic result if passed in ---------
def _stub(img: Image.Image, heuristic: Optional[Dict[str,Any]]) -> Dict[str,Any]:
    if heuristic:
        return {"label": heuristic.get("label","Criollo/Mix"),
                "class": heuristic.get("class","CRIOLLO"),
                "conf": float(heuristic.get("conf",0.55)),
                "reason": heuristic.get("reason","(stub) heurística"), "source":"ai_stub"}
    return {"label":"Criollo/Mix","class":"CRIOLLO","conf":0.45,"reason":"(stub) sin evidencia fuerte","source":"ai_stub"}

def run_breed_ai(img: Image.Image, cfg: Dict[str, Any], heuristic: Optional[Dict[str,Any]] = None) -> Dict[str,Any]:
    prov = (cfg.get("breed_ai",{}) or {}).get("provider","stub")
    if prov == "openai":
        ans = _call_openai(img, model=(cfg.get("breed_ai",{}).get("model","gpt-4o-mini")))
        if ans: return ans
        # fallthrough -> stub if allowed
    # default / stub
    return _stub(img, heuristic)
