
from typing import Dict, Any
import numpy as np
from PIL import Image

PROMPT_SISTEMA = """
Eres un evaluador de ENRAZAMIENTO visual de ganado en fotos laterales.
- Señales de ENRAZADO (cebú/Brahman): orejas largas caídas, papada/gancho de piel marcada (dewlap), giba/hump en la cruz.
- Si hay ≥1–2 señales fuertes → clasifica ENRAZADO (o "Brahman/Mix").
- Si las señales son leves → MIX.
- Solo CRIOLLO cuando NO hay señales claras de cebú.
Devuelve: {"label":"Brahman/Mix|Criollo/Mix|Criollo", "class":"ENRAZADO|CRIOLLO", "conf":0..1, "scores":{"ears":..,"dewlap":..,"hump":..}, "reason": "..."}.
"""

def _to_np(img: Image.Image):
    return np.asarray(img.convert("RGB"))

def _edge_energy(gray: np.ndarray) -> float:
    g = gray.astype(np.float32) / 255.0
    gx = np.zeros_like(g); gy = np.zeros_like(g)
    gx[:,1:-1] = g[:,2:] - g[:,:-2]; gy[1:-1,:] = g[2:,:] - g[:-2,:]
    return float(np.mean(np.abs(gx)) + np.mean(np.abs(gy)))

def _roi(img: np.ndarray, y0: float, y1: float, x0: float, x1: float) -> np.ndarray:
    h, w = img.shape[:2]
    r0, r1 = int(h*y0), int(h*y1)
    c0, c1 = int(w*x0), int(w*x1)
    r0 = max(0,min(h-1,r0)); r1 = max(r0+1,min(h, r1))
    c0 = max(0,min(w-1,c0)); c1 = max(c0+1,min(w, c1))
    return img[r0:r1, c0:c1, :]

def _ears_score(rgb: np.ndarray) -> float:
    h, w, _ = rgb.shape
    head = _roi(rgb, 0.1, 0.5, 0.0, 0.45)
    gray = np.mean(head, axis=2)
    e = _edge_energy(gray)
    dark_ratio = float((gray < 120).mean())
    s = min(1.0, 0.6*e/0.02 + 0.4*dark_ratio)
    return s

def _dewlap_score(rgb: np.ndarray) -> float:
    neck = _roi(rgb, 0.35, 0.75, 0.15, 0.55)
    gray = np.mean(neck, axis=2)
    e = _edge_energy(gray)
    col_var = float(np.var(gray.mean(axis=1)))
    s = min(1.0, 0.7*e/0.02 + 0.3*min(1.0, col_var/400.0))
    return s

def _hump_score(rgb: np.ndarray) -> float:
    withers = _roi(rgb, 0.10, 0.35, 0.30, 0.65)
    gray = np.mean(withers, axis=2)
    h = gray.shape[0]
    if h < 3: return 0.0
    row_mean = gray.mean(axis=1)
    center = float(row_mean[h//3:2*h//3].mean())
    edges = float(np.r_[row_mean[:h//3], row_mean[2*h//3:]].mean())
    prom = max(0.0, edges - center) / 80.0
    e = _edge_energy(gray)
    s = min(1.0, 0.6*prom + 0.4*e/0.02)
    return s

def run_breed_heuristic(img: Image.Image, cfg: Dict[str, Any]) -> Dict[str, Any]:
    rgb = _to_np(img)
    bw = cfg.get("breed", {}).get("weights", {"ears":0.35,"dewlap":0.40,"hump":0.25})
    zebu_hi = float(cfg.get("breed", {}).get("zebu_hi", 0.55))
    zebu_lo = float(cfg.get("breed", {}).get("zebu_lo", 0.40))

    ears = _ears_score(rgb)
    dewlap = _dewlap_score(rgb)
    hump = _hump_score(rgb)

    zebu_score = float(bw.get("ears",0.35))*ears + float(bw.get("dewlap",0.40))*dewlap + float(bw.get("hump",0.25))*hump

    if zebu_score >= zebu_hi:
        label = "Brahman/Mix"
        clazz = "ENRAZADO"
        conf = min(1.0, 0.65 + 0.35*(zebu_score- zebu_hi)/(1.0 - zebu_hi + 1e-6))
    elif zebu_score >= zebu_lo:
        label = "Criollo/Mix"
        clazz = "ENRAZADO"
        conf = 0.55 + 0.30*(zebu_score - zebu_lo)/(zebu_hi - zebu_lo + 1e-6)
    else:
        label = "Criollo/Mix"
        clazz = "CRIOLLO"
        conf = 0.60 - 0.40*(zebu_score / (zebu_lo + 1e-6))

    reason = f"zebu_score={zebu_score:.2f} (ears={ears:.2f}, dewlap={dewlap:.2f}, hump={hump:.2f}). " +              ("Señales claras de cebú." if clazz=='ENRAZADO' else "Sin señales fuertes de cebú.")
    return {"label":label, "class":clazz, "conf":round(conf,2),
            "zebu_score":round(zebu_score,2),
            "scores":{"ears":round(ears,2), "dewlap":round(dewlap,2), "hump":round(hump,2)},
            "reason":reason}
