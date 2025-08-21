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
