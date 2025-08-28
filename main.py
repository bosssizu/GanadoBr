# main.py
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from openai import AsyncOpenAI
import json, base64, os as osmod, asyncio, hashlib

import prompts

ALLOWED_DECISIONS = {"NO_COMPRAR","CONSIDERAR_BAJO","CONSIDERAR_ALTO","COMPRAR"}

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

client = AsyncOpenAI()

def clamp(v, lo=1.0, hi=10.0):
    return max(lo, min(hi, v))

def snap05(v):
    return round(v * 2) / 2.0

def normalize_rubric(rubric):
    for item in rubric:
        try:
            s = float(item["score"])
            item["score"] = clamp(snap05(s))
        except Exception:
            item["score"] = 5.0
    return rubric

def img_hash(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

RUBRIC_CACHE = {}
HEALTH_BREED_CACHE = {}

async def run_prompt(prompt, category=None, input_data=None, image_bytes=None):
    # inyecta categoría solo si se provee (solo PROMPT_3)
    if category:
        prompt = prompt.replace("{category}", category)

    # fuerza español + JSON
    prompt = prompt + "\n\nResponde SIEMPRE en español. Devuelve SOLO JSON válido."

    if image_bytes:
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        resp = await client.chat.completions.create(
            model="gpt-4o",
            temperature=0,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": [
                    {"type": "text", "text": "Analiza esta imagen y devuelve solo JSON."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                ]}
            ],
            response_format={"type": "json_object"}
        )
    else:
        resp = await client.chat.completions.create(
            model="gpt-4o",
            temperature=0,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(input_data)}
            ],
            response_format={"type": "json_object"}
        )
    return json.loads(resp.choices[0].message.content)

@app.get("/")
async def root():
    return FileResponse(osmod.path.join("static", "index.html"))

def fallback_decision_from_score(gs: float):
    if gs < 6.2:
        return "NO_COMPRAR", "No comprar"
    if gs < 7.2:
        return "CONSIDERAR_BAJO", "Considerar (bajo)"
    if gs < 8.2:
        return "CONSIDERAR_ALTO", "Considerar alto"
    return "COMPRAR", "Comprar"

@app.post("/api/evaluate")
async def evaluate(category: str = Form(...), file: UploadFile = File(...)):
    try:
        img = await file.read()
        key = img_hash(img)

        # Morfología cacheada por imagen (no depende de categoría)
        if key in RUBRIC_CACHE:
            rubric = RUBRIC_CACHE[key]
        else:
            res1 = await run_prompt(prompts.PROMPT_1, None, None, img)
            res2 = await run_prompt(prompts.PROMPT_2, None, res1)
            rubric = normalize_rubric(res2["rubric"])
            RUBRIC_CACHE[key] = rubric

        # Salud/Raza cacheadas por imagen
        if key in HEALTH_BREED_CACHE:
            res4, res5 = HEALTH_BREED_CACHE[key]
        else:
            health_task = asyncio.create_task(run_prompt(prompts.PROMPT_4, None, None, img))
            breed_task = asyncio.create_task(run_prompt(prompts.PROMPT_5, None, None, img))
            res4, res5 = await asyncio.gather(health_task, breed_task)
            HEALTH_BREED_CACHE[key] = (res4, res5)

        # Decisión depende de categoría
        res3 = await run_prompt(prompts.PROMPT_3, category, {"rubric": rubric})

        decision = res3
        if "decision_level" not in decision or decision.get("decision_level") not in ALLOWED_DECISIONS:
            gs = float(decision.get("global_score", 0))
            level, text = fallback_decision_from_score(gs)
            decision = {
                "global_score": gs,
                "weighted_score": decision.get("weighted_score", gs),
                "band_score": decision.get("band_score", gs),
                "decision_level": level,
                "decision_text": text,
                "rationale": decision.get("rationale", "Ajustado automáticamente para cumplir el formato.")
            }

        return {
            "engine": "ai",
            "category": category,
            "rubric": rubric,
            "decision": decision,
            "health": res4["health"],
            "breed": res5["breed"]
        }
    except Exception as e:
        return {"error": str(e)}
