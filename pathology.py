
from typing import Any, Dict, List, Tuple
import numpy as np
from PIL import Image
import json, pathlib

def _load_cfg() -> Dict[str, Any]:
    p = pathlib.Path("config.json")
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

CFG = _load_cfg()

def _to_np_rgb(img: Image.Image) -> np.ndarray:
    return np.asarray(img.convert("RGB"))

def _saturation(rgb: np.ndarray) -> np.ndarray:
    r = rgb[:,:,0].astype(np.float32)/255.0
    g = rgb[:,:,1].astype(np.float32)/255.0
    b = rgb[:,:,2].astype(np.float32)/255.0
    mx = np.maximum(r, np.maximum(g,b))
    mn = np.minimum(r, np.minimum(g,b))
    s = np.zeros_like(mx)
    nz = mx > 1e-6
    s[nz] = (mx[nz]-mn[nz]) / mx[nz]
    return s

def _red_like(rgb: np.ndarray) -> np.ndarray:
    R = rgb[:,:,0].astype(np.float32)
    G = rgb[:,:,1].astype(np.float32)
    B = rgb[:,:,2].astype(np.float32)
    s = _saturation(rgb)
    return (R > 140) & (R > G + 20) & (R > B + 20) & (s > 0.35)

def _blur_score(img: Image.Image) -> float:
    g = np.asarray(img.convert("L"), dtype=np.float32) / 255.0
    gx = np.zeros_like(g); gy = np.zeros_like(g)
    gx[:,1:-1] = g[:,2:] - g[:,:-2]; gy[1:-1,:] = g[2:,:] - g[:-2,:]
    return float(np.var(gx) + np.var(gy))

def _cc_label(mask: np.ndarray) -> Tuple[np.ndarray, List[Tuple[int,int,int,int,int]]]:
    h, w = mask.shape
    labels = np.zeros((h,w), dtype=np.int32)
    comp = []; cur = 0
    visited = np.zeros_like(mask, dtype=bool)
    for r in range(h):
        for c in range(w):
            if not mask[r,c] or visited[r,c]: continue
            cur += 1
            stack=[(r,c)]; visited[r,c]=True; labels[r,c]=cur
            minr,minc,maxr,maxc = r,c,r,c; area=0
            while stack:
                rr,cc = stack.pop()
                area += 1
                if rr<minr: minr=rr
                if rr>maxr: maxr=rr
                if cc<minc: minc=cc
                if cc>maxc: maxc=cc
                for dr,dc in ((1,0),(-1,0),(0,1),(0,-1)):
                    nr, nc = rr+dr, cc+dc
                    if 0<=nr<h and 0<=nc<w and mask[nr,nc] and not visited[nr,nc]:
                        visited[nr,nc]=True; labels[nr,nc]=cur; stack.append((nr,nc))
            comp.append((area,minr,minc,maxr,maxc))
    return labels, comp

def _shape_features(mask: np.ndarray, bbox: Tuple[int,int,int,int]) -> Dict[str,float]:
    minr,minc,maxr,maxc = bbox
    sub = mask[minr:maxr+1, minc:maxc+1]
    area = float(sub.sum())
    h, w = sub.shape
    bbox_area = float(h*w) if h*w>0 else 1.0
    extent = area / bbox_area
    aspect = (w / max(1,h))
    shp = CFG.get("pathology",{}).get("shape",{})
    oval = (extent >= float(shp.get("extent_min", 0.45)) and
            float(shp.get("oval_aspect_lo", 0.6)) <= aspect <= float(shp.get("oval_aspect_hi", 1.8)))
    return {"extent": extent, "aspect": aspect, "oval": float(oval)}

def _roi(img: np.ndarray, y0: float, y1: float, x0: float, x1: float) -> np.ndarray:
    h, w, _ = img.shape
    r0, r1 = int(h*y0), int(h*y1)
    c0, c1 = int(w*x0), int(w*x1)
    r0 = max(0,min(h-1,r0)); r1 = max(r0+1,min(h, r1))
    c0 = max(0,min(w-1,c0)); c1 = max(c0+1,min(w, c1))
    return img[r0:r1, c0:c1, :]

def _analyze_region(rgb: np.ndarray) -> Dict[str, Any]:
    mask = _red_like(rgb)
    labels, comps = _cc_label(mask)
    h, w, _ = rgb.shape
    img_area = h*w
    shp_cfg = CFG.get("pathology",{}).get("shape",{})
    min_ar = float(shp_cfg.get("min_area_ratio", 0.0008)) * img_area
    max_ar = float(shp_cfg.get("max_area_ratio", 0.08))    * img_area
    best = {"area":0,"bbox":(0,0,0,0),"oval":0.0,"extent":0.0,"aspect":0.0}
    total_red = float(mask.mean())
    for area,minr,minc,maxr,maxc in comps:
        if area < min_ar or area > max_ar: continue
        feats = _shape_features(mask, (minr,minc,maxr,maxc))
        score = area * (0.5 + 0.5*feats["oval"]) * (0.5 + 0.5*feats["extent"])
        if score > best["area"]:
            best = {"area":area,"bbox":(minr,minc,maxr,maxc),"oval":feats["oval"],"extent":feats["extent"],"aspect":feats["aspect"]}
    return {"total_red": total_red, "best": best, "mask_count": len(comps), "h":h, "w":w}

def run_pathology_heuristic(img: Image.Image, mode: str, vis_ratio: float) -> Dict[str, Any]:
    cfgp = CFG.get("pathology", {}) or {}
    alert_thr = float(cfgp.get("alert_threshold", 0.80))
    confirm_thr = float(cfgp.get("confirm_threshold", 0.90))
    checks = (cfgp.get("checklist", {}) or {}).get(mode, [])

    blur = _blur_score(img)
    rgb = _to_np_rgb(img)

    out: List[Dict[str,Any]] = []

    # Lesión cutánea
    if "lesion_cutanea" in checks:
        anal = _analyze_region(rgb)  # toda la imagen
        base_conf = 0.0
        if anal["total_red"] > 0.035: base_conf = 0.86
        elif anal["total_red"] > 0.015: base_conf = 0.78
        shape_ok = (anal["best"]["oval"] >= 0.5) and (anal["best"]["area"] > 0)
        if shape_ok: base_conf = max(base_conf, 0.90)  # solo forma válida habilita confirmación
        conf = base_conf
        if blur < 0.0008: conf -= 0.08
        if vis_ratio < 0.55: conf -= 0.05
        conf = max(0.0, min(0.99, conf))
        if conf >= confirm_thr and shape_ok:
            sev = "confirmada"
        elif conf >= alert_thr:
            sev = "alerta"
        else:
            sev = "descartado"
        out.append({"name":"lesion_cutanea","present": (sev!="descartado"), "confidence": round(conf,2),
                    "severity": sev, "shape_ok": bool(shape_ok),
                    "notes": f"rojo≈{round(anal['total_red']*100,1)}%, oval={int(anal['best']['oval'])}, extent≈{anal['best']['extent']:.2f}"})

    # Ojo infectado (ROI frontal-superior)
    if "ojo_infectado" in checks:
        h, w, _ = rgb.shape
        roi = rgb[:int(h*0.35), :int(w*0.35), :]
        anal = _analyze_region(roi)
        base_conf = 0.0
        if anal["total_red"] > 0.02 and anal["best"]["area"]>0: base_conf = 0.82
        shape_ok = (anal["best"]["oval"] >= 0.5) and (0.0002*h*w <= anal["best"]["area"] <= 0.005*h*w)
        if shape_ok: base_conf = max(base_conf, 0.90)  # forma/ubicación correctas → posible confirmada
        conf = base_conf
        if blur < 0.0008: conf -= 0.08
        if vis_ratio < 0.55: conf -= 0.05
        conf = max(0.0, min(0.97, conf))
        if conf >= confirm_thr and shape_ok:
            sev = "confirmada"
        elif conf >= alert_thr:
            sev = "alerta"
        else:
            sev = "descartado"
        out.append({"name":"ojo_infectado","present": (sev!="descartado"), "confidence": round(conf,2),
                    "severity": sev, "shape_ok": bool(shape_ok),
                    "notes": f"oval={int(anal['best']['oval'])}, extent≈{anal['best']['extent']:.2f}"})

    # Prolapso (ROI caudal-inferior) — exige forma oval para confirmada
    if "prolapso" in checks:
        h, w, _ = rgb.shape
        roi = rgb[int(h*0.55):, int(w*0.55):, :]
        anal = _analyze_region(roi)
        base_conf = 0.0
        if anal["total_red"] > 0.02 and anal["best"]["area"]>0: base_conf = 0.84
        shape_ok = (anal["best"]["oval"] >= 0.5)
        if shape_ok: base_conf = max(base_conf, 0.90)
        conf = base_conf
        if blur < 0.0008: conf -= 0.08
        if vis_ratio < 0.55: conf -= 0.05
        conf = max(0.0, min(0.99, conf))
        if conf >= confirm_thr and shape_ok:
            sev = "confirmada"
        elif conf >= alert_thr:
            sev = "alerta"
        else:
            sev = "descartado"
        out.append({"name":"prolapso","present": (sev!="descartado"), "confidence": round(conf,2),
                    "severity": sev, "shape_ok": bool(shape_ok),
                    "notes": f"oval={int(anal['best']['oval'])}, extent≈{anal['best']['extent']:.2f}"})

    # Cojera — nunca confirmada con este proxy
    if "cojera" in checks:
        a = np.asarray(img.convert("L"))
        h, w = a.shape
        roi = a[int(h*0.55):, int(w*0.45):]
        gx = np.zeros_like(roi, dtype=np.float32); gy = np.zeros_like(roi, dtype=np.float32)
        gx[:,1:-1] = roi[:,2:] - roi[:,:-2]; gy[1:-1,:] = roi[2:,:] - roi[:-2,:]
        e = float(np.mean(np.abs(gx)) + np.mean(np.abs(gy)))
        conf = 0.0
        if e < 0.004: conf = 0.55
        elif e < 0.006: conf = 0.65
        else: conf = 0.40
        if blur < 0.0008: conf -= 0.05
        conf = max(0.0, min(0.85, conf))
        sev = "alerta" if conf >= alert_thr else "descartado"
        out.append({"name":"cojera","present": (sev!='descartado'), "confidence": round(conf,2),
                    "severity": sev, "shape_ok": False, "notes": ""})

    return {"health": out, "blur_score": blur}
