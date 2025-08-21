
from typing import Any, Dict, List, Tuple
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
import statistics, json, pathlib

Heuristic = Dict[str, Any]

def _load_cfg() -> Dict[str, Any]:
    p = pathlib.Path("config.json")
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

CFG = _load_cfg()

def _prep(img: Image.Image, target_max: int = 512) -> np.ndarray:
    w, h = img.size
    scale = target_max / max(w, h)
    if scale < 1.0:
        img = img.resize((int(w*scale), int(h*scale)))
    g = img.convert("L")
    arr = np.asarray(g, dtype=np.float32) / 255.0
    return arr

def _gradients(arr: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    gx = np.zeros_like(arr)
    gy = np.zeros_like(arr)
    gx[:,1:-1] = arr[:,2:] - arr[:,:-2]
    gy[1:-1,:] = arr[2:,:] - arr[:-2,:]
    mag = np.sqrt(gx*gx + gy*gy)
    return gx, gy, mag

def _band(arr: np.ndarray, y0: float, y1: float, x0: float=0.0, x1: float=1.0) -> np.ndarray:
    h, w = arr.shape
    r0, r1 = int(h*y0), int(h*y1)
    c0, c1 = int(w*x0), int(w*x1)
    r0 = max(0, min(h-1, r0)); r1 = max(r0+1, min(h, r1))
    c0 = max(0, min(w-1, c0)); c1 = max(c0+1, min(w, c1))
    return arr[r0:r1, c0:c1]

def _straightness_score(arr: np.ndarray) -> float:
    mag = np.abs(arr)
    if mag.size == 0: return 3.0
    y_idx = np.argmax(mag, axis=0)
    if y_idx.size < 2: return 3.0
    var = float(np.var(y_idx))
    if var < 2.0: return 4.2
    if var < 5.0: return 3.6
    if var < 9.0: return 3.2
    return 2.8

def _ribs_visible(gx_center: np.ndarray, thresh: float=0.08) -> bool:
    v = float(np.mean(np.abs(gx_center)))
    return v > thresh

def _posterior_score(mag_lr: np.ndarray) -> float:
    if mag_lr.size == 0: return 3.3
    edge = float(np.mean(mag_lr))
    if edge < 0.03: return 4.0
    if edge < 0.06: return 3.6
    if edge < 0.09: return 3.3
    return 3.0

def _whiteness(arr: np.ndarray) -> float:
    return float((arr > 0.75).mean())

def run_single_pass(image: Image.Image, target_max: int = 512):
    arr = _prep(image, target_max=target_max)
    gx, gy, mag = _gradients(arr)

    brightness = float(arr.mean())
    contrast   = float(arr.std())

    center_band    = _band(gx, 0.35, 0.65, 0.15, 0.85)
    back_band      = _band(gy, 0.18, 0.32, 0.10, 0.90)
    posterior_zone = _band(mag, 0.45, 0.95, 0.65, 0.98)

    ribs = _ribs_visible(center_band, thresh=0.08 if contrast>0.18 else 0.06)
    backline_score = _straightness_score(back_band)
    posterior      = _posterior_score(posterior_zone)

    thorax   = "high" if brightness>0.58 else ("med" if brightness>0.45 else "low")
    abdomen  = "high" if (brightness>0.55 and contrast<0.20) else ("med" if brightness>0.42 else "low")
    backline = "good" if backline_score>=4.0 else ("ok" if backline_score>=3.4 else "poor")

    if ribs and contrast>0.20: bcs = 2.5
    elif ribs: bcs = 2.8
    else: bcs = 3.2 if brightness>0.5 else 3.0

    white = _whiteness(arr)
    if white > 0.40:
        breed = {"class":"ENRAZADO","label":"Brahman/Mix","conf":0.80}
    elif white < 0.20:
        breed = {"class":"CRIOLLO","label":"Criollo/Mix","conf":0.60}
    else:
        breed = {"class":"MIXTO","label":"Mixto","conf":0.65}

    return {
        "bcs_1_5": {"value": round(bcs,1), "conf": 0.70},
        "capacity": {"thorax_depth": thorax, "abdomen": abdomen, "backline": backline, "conf": 0.65},
        "posterior": {"muscle": "high" if posterior>=3.8 else ("med" if posterior>=3.3 else "low"), "conf": 0.65},
        "cues": {"ribs": str(ribs).lower(), "hooks_pins":"na","tailhead_fat":"na","brisket_fat":"na"},
        "breed": breed,
        "flags": {"lameness": "na","lesion":"na"},
        "stats": {"brightness":brightness, "contrast":contrast, "white": white}
    }

def _obs_cabeza(breed_class: str, bcs: float) -> str:
    if breed_class == "ENRAZADO":
        return "Cabeza cebuina; cuello fino" if bcs <= 3.0 else "Cabeza cebuina; cuello proporcionado"
    if breed_class == "CRIOLLO":
        return "Cabeza criolla; proporciones moderadas"
    return "Cabeza proporcionada; cuello medio"

def _obs_dorsal(backline: str) -> str:
    return {"good":"Línea dorsal recta/buena","ok":"Línea dorsal aceptable","poor":"Línea dorsal algo caída"}\
        .get(backline, "Línea dorsal aceptable")

def _obs_torax(thorax: str) -> str:
    return {"high":"Pecho profundo","med":"Pecho aceptable","low":"Pecho escaso"}\
        .get(thorax, "Pecho aceptable")

def _obs_costillas(ribs: bool) -> str:
    return "Costillas marcadas" if ribs else "Costillas poco visibles"

def _obs_posterior(level: str) -> str:
    return {"high":"Muslo lleno","med":"Muslo medio","low":"Muslo escaso"}\
        .get(level, "Muslo medio")

def _obs_cola_grupa(backline: str) -> str:
    return "Grupa algo caída" if backline in ("poor","ok") else "Grupa correcta"

def _obs_piel_pelo(white: float) -> str:
    return "Pelo claro/liso" if white>0.4 else ("Pelo oscuro o mixto" if white<0.2 else "Pelo mixto; limpio")

def _rubric_from_heuristic(h):
    cap = h.get("capacity",{}) or {}
    pos = h.get("posterior",{}) or {}
    bcs = float(h.get("bcs_1_5",{}).get("value") or 3.0)

    thorax   = str(cap.get("thorax_depth","med")).lower()
    abdomen  = str(cap.get("abdomen","med")).lower()
    backline = str(cap.get("backline","ok")).lower()
    posterior_level = str(pos.get("muscle","med")).lower()

    thorax_sc = {"low": 2.5, "med": 3.4, "high": 4.2}.get(thorax, 3.4)
    abd_sc    = {"low": 2.6, "med": 3.4, "high": 4.3}.get(abdomen, 3.4)
    back_sc   = {"poor": 2.8, "ok": 3.5, "good": 4.2}.get(backline, 3.5)
    post_sc   = {"low": 2.8, "med": 3.3, "high": 4.2}.get(posterior_level, 3.3)

    ribs = str((h.get("cues",{}) or {}).get("ribs")).lower() == "true"
    costillar_sc = 3.0 if ribs else 3.6

    breed_class = (h.get("breed") or {}).get("class","MIXTO")
    white = float((h.get("stats") or {}).get("white") or 0.3)

    rubric = [
        {"key":"cabeza_cuello", "name":"Cabeza y cuello", "score": 3.2, "obs": _obs_cabeza(breed_class, bcs)},
        {"key":"linea_dorsal", "name":"Línea dorsal (lomo)", "score": back_sc, "obs": _obs_dorsal(backline)},
        {"key":"prof_toracica", "name":"Profundidad torácica", "score": thorax_sc, "obs": _obs_torax(thorax)},
        {"key":"costillar", "name":"Costillar", "score": costillar_sc, "obs": _obs_costillas(ribs)},
        {"key":"grupo_posterior", "name":"Grupo posterior (anca, muslos, nalgas)", "score": post_sc, "obs": _obs_posterior(posterior_level)},
        {"key":"aplomos", "name":"Aplomos (miembros)", "score": 3.6, "obs":"Aplomos rectos (sin evidencia de cojera)"},
        {"key":"cola_grupa", "name":"Inserción de cola y grupa", "score": 3.1, "obs": _obs_cola_grupa(backline)},
        {"key":"piel_pelo", "name":"Piel y pelo", "score": 3.8, "obs": _obs_piel_pelo(white)},
        {"key":"bcs", "name":"Condición corporal (BCS)", "score": round(bcs,1), "obs":"Escala 1–5 (estimado)"}
    ]
    return rubric

DEFAULT_WEIGHTS_BY_MODE = {
    "levante": {"bcs":0.30, "grupo_posterior":0.10, "aplomos":0.05, "linea_dorsal":0.12, "prof_toracica":0.12, "costillar":0.07, "cabeza_cuello":0.04, "cola_grupa":0.04, "piel_pelo":0.06},
    "engorde": {"bcs":0.30, "grupo_posterior":0.30, "aplomos":0.05, "linea_dorsal":0.08, "prof_toracica":0.08, "costillar":0.04, "cola_grupa":0.05, "piel_pelo":0.10, "cabeza_cuello":0.00},
    "vaca_flaca": {"bcs":0.40, "aplomos":0.25, "linea_dorsal":0.08, "prof_toracica":0.08, "costillar":0.04, "piel_pelo":0.10, "cabeza_cuello":0.04, "cola_grupa":0.01, "grupo_posterior":0.00},
}
WEIGHTS_BY_MODE = CFG.get("weights_by_mode", DEFAULT_WEIGHTS_BY_MODE)

def _decision_with_sublevels(t: float):
    dcfg = CFG.get("decision_sublevels", {})
    no_max = float(dcfg.get("no_comprar_max", 2.9))
    c_low = float(dcfg.get("considerar_bajo_max", 3.2))
    c_hi  = float(dcfg.get("considerar_alto_max", 3.7))
    if t < no_max:
        return "NO_COMPRAR", "NO COMPRAR", ""
    elif t <= c_low:
        return "CONSIDERAR_BAJO", "CONSIDERAR (bajo)", "Solo si precio bajo."
    elif t <= c_hi:
        return "CONSIDERAR_ALTO", "CONSIDERAR (alto)", "Vale si condiciones son buenas."
    else:
        return "COMPRAR", "COMPRAR", ""

def _weighted_total_1to5(rubric, breed, vis_ratio, mode: str):
    w = WEIGHTS_BY_MODE.get(mode, WEIGHTS_BY_MODE["levante"])
    total_w = sum(w.get(r["key"], 0.0) for r in rubric)
    if total_w <= 0: total_w = 1.0
    total_1to5 = sum(r["score"] * (w.get(r["key"], 0.0)/total_w) for r in rubric)

    breed_class = (breed or {}).get("class","MIXTO")
    breed_conf = float((breed or {}).get("conf") or 0.0)
    breed_adj = 0.0
    if breed_class == "ENRAZADO" and breed_conf >= 0.75:
        breed_adj = 0.10
    elif breed_class == "CRIOLLO":
        breed_adj = -0.10
    total_1to5 = max(1.0, min(5.0, total_1to5 + breed_adj))

    caps = CFG.get("visibility_caps", {})
    cap35 = float(caps.get("lt_0_35", 3.5))
    cap55 = float(caps.get("lt_0_55", 3.9))
    if vis_ratio < 0.35: total_1to5 = min(total_1to5, cap35)
    elif vis_ratio < 0.55: total_1to5 = min(total_1to5, cap55)

    level, label, hint = _decision_with_sublevels(total_1to5)
    return {"total_1to5": round(total_1to5,2), "decision_level": level, "decision_label": label, "decision_hint": hint, "breed_adj": breed_adj, "weights_used": w}

def _evidence_score_1to5(vis_ratio: float, h) -> float:
    contrast = float(((h.get("stats") or {}).get("contrast")) or 0.15)
    vis_term = vis_ratio
    ctr_term = min(0.35, max(0.05, contrast)) / 0.35
    score = 5.0 * (0.4*vis_term + 0.6*ctr_term)
    return float(round(score,2))

def _rubric_sigma(rubric) -> float:
    vals = [r["score"] for r in rubric]
    if len(vals) < 2: return 0.0
    return float(np.std(vals))

def _conflict_flags(h) -> bool:
    ribs = str((h.get("cues",{}) or {}).get("ribs")).lower() == "true"
    bcs = float(h.get("bcs_1_5",{}).get("value") or 3.0)
    return bool(ribs and bcs >= 3.5)

def _crop_variants(img: Image.Image):
    w, h = img.size; crops = []
    for frac in (0.92, 0.88):
        cw, ch = int(w*frac), int(h*frac)
        for dx in (-int(w*0.04), 0, int(w*0.04)):
            x0 = max(0, min(w-cw, (w-cw)//2 + dx))
            y0 = max(0, (h-ch)//2)
            crops.append(img.crop((x0,y0,x0+cw,y0+ch)))
    return crops[:3]

def _jitter_variants(img: Image.Image):
    out = []
    out.append(ImageEnhance.Brightness(img).enhance(1.05))
    out.append(ImageEnhance.Contrast(img).enhance(0.95))
    out.append(img.filter(ImageFilter.GaussianBlur(radius=0.5)))
    return out

def _majority_label(labels):
    return max(set(labels), key=labels.count) if labels else "MIXTO"

def second_pass_ensemble(img: Image.Image, vis_ratio: float):
    variants = [img] + _crop_variants(img) + _jitter_variants(img)
    per_rubrics = []
    breeds, breed_confs = [], []
    hrefs = []
    for i, im in enumerate(variants):
        target_max = 512 if (i % 2 == 0) else 384
        h = run_single_pass(im, target_max=target_max); hrefs.append(h)
        per_rubrics.append(_rubric_from_heuristic(h))
        br = h.get("breed") or {}
        breeds.append(br.get("class","MIXTO")); breed_confs.append(float(br.get("conf") or 0.0))
    keys = [r["key"] for r in _rubric_from_heuristic(run_single_pass(img))]
    name_map = {r["key"]: r["name"] for r in per_rubrics[0]}
    obs_map  = {r["key"]: r["obs"] for r in per_rubrics[0]}
    scores_by_key = {k: [] for k in keys}
    for rub in per_rubrics:
        for r in rub:
            scores_by_key[r["key"]].append(float(r["score"]))
    def mad(vals):
        import statistics
        m = statistics.median(vals); return float(statistics.median([abs(x-m) for x in vals]))
    rubric_agg = []
    SI_items = {}
    for k in keys:
        vs = scores_by_key[k]; med = float(__import__("statistics").median(vs)); mad_v = mad(vs)
        SI_r = 1.0 - min(1.0, mad_v / 1.5); SI_items[name_map[k]] = round(SI_r,2)
        rubric_agg.append({"key":k, "name":name_map[k], "score":round(med,2), "obs":obs_map[k]})
    majority = _majority_label(breeds)
    best_idx = int(np.argmax(breed_confs))
    breed_agg = (hrefs[best_idx].get("breed") or {"class":majority, "label":majority, "conf":0.7})
    very_imp_names = {"Grupo posterior (anca, muslos, nalgas)","Línea dorsal (lomo)","Profundidad torácica","Condición corporal (BCS)"}
    si_vals = [v for n,v in SI_items.items() if n in very_imp_names]
    SI_global = round(sum(si_vals)/len(si_vals), 2) if si_vals else 0.7
    return {"rubric": rubric_agg, "breed": breed_agg, "SI_items": SI_items, "SI_global": SI_global, "n": len(variants)}

def run_auction_heuristics(image_bgr: Image.Image):
    return run_single_pass(image_bgr)

def apply_heuristic_scoring(d_in, first_h):
    d = dict(d_in); d.setdefault("reasons", []); d.setdefault("qc", {}); d.setdefault("ux", {})
    mode = d.get("mode", "levante")
    vis_ratio = float(d.get("qc",{}).get("visible_ratio") or 0.5)
    d["qc"]["auction_mode"] = True

    rubric1 = _rubric_from_heuristic(first_h); breed1  = first_h.get("breed") or {}
    totals1 = _weighted_total_1to5(rubric1, breed1, vis_ratio, mode)

    evidence = _evidence_score_1to5(vis_ratio, first_h); sigma = _rubric_sigma(rubric1); conflicts = _conflict_flags(first_h)
    low_conf_cnt = sum([ (float(first_h.get("bcs_1_5",{}).get("conf") or 0.0) < 0.6),
                         (float(first_h.get("capacity",{}).get("conf") or 0.0) < 0.6),
                         (float(first_h.get("posterior",{}).get("conf") or 0.0) < 0.6) ])
    borderline = (3.2 <= totals1["total_1to5"] <= 3.4) or (3.9 <= totals1["total_1to5"] <= 4.1)
    trigger = (evidence < 3.5) or (vis_ratio < 0.55) or borderline or (sigma > 0.6) or conflicts or (low_conf_cnt>=2)

    used_second = False; SI_global=None; SI_items=None; weights_used = totals1["weights_used"]
    if trigger:
        ensemble = second_pass_ensemble(d_in.get("raw_image"), vis_ratio)
        rubric = ensemble["rubric"]; breed  = ensemble["breed"]
        totals = _weighted_total_1to5(rubric, breed, vis_ratio, mode)
        SI_global = ensemble["SI_global"]; SI_items  = ensemble["SI_items"]; used_second = True; weights_used = totals["weights_used"]
    else:
        rubric, breed, totals = rubric1, breed1, totals1

    d["rubric"] = [{"name": r["name"], "score": r["score"], "obs": r["obs"]} for r in rubric]
    d["breed"] = breed
    d["total_1to5"] = totals["total_1to5"]
    d["total"] = totals["total_1to5"]
    d["decision_level"] = totals["decision_level"]
    d["decision"] = totals["decision_label"]
    if totals.get("decision_hint"): d["reasons"].append(totals["decision_hint"])
    d["global_conf"] = float(first_h.get("bcs_1_5",{}).get("conf") or 0.6)
    d["ux"]["angles_tooltip"] = "Ángulos omitidos en subasta."
    d["ux"]["weights_used"] = weights_used
    d["diagnostics"] = {"evidence": evidence, "sigma_rubric": sigma, "borderline": borderline,
                        "conflict_ribs_bcs": conflicts, "low_conf_count": int(low_conf_cnt),
                        "second_pass_used": used_second, "SI_global": SI_global, "SI_items": SI_items}
    d["reasons"].append(f"Pesos por modo: {mode}.")
    if used_second:
        d["reasons"].append(f"2ª pasada de confirmación ejecutada; SI={SI_global}.")
    if SI_global is not None:
        if SI_global >= 0.75: d["ux"]["stability"] = {"level":"estable","si":SI_global}
        elif SI_global >= 0.55: d["ux"]["stability"] = {"level":"moderado","si":SI_global}
        else: d["ux"]["stability"] = {"level":"inestable","si":SI_global}
    return d
