# main.py
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from openai import AsyncOpenAI
import json
import os as osmod
import prompts
import base64

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

client = AsyncOpenAI()

async def run_prompt(prompt, category=None, input_data=None, image_bytes=None):
    if category:
        prompt = prompt.replace("{category}", category)

    if image_bytes:
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        resp = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": [
                    {"type": "text", "text": "Analyze this image and return JSON."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                ]}
            ],
            response_format={"type": "json_object"}
        )
    else:
        resp = await client.chat.completions.create(
            model="gpt-4o",
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

@app.post("/api/evaluate")
async def evaluate(category: str = Form(...), file: UploadFile = File(...)):
    try:
        img = await file.read()

        res1 = await run_prompt(prompts.PROMPT_1, category, None, img)
        res2 = await run_prompt(prompts.PROMPT_2, category, res1)
        res3 = await run_prompt(prompts.PROMPT_3, category, res2)
        res4 = await run_prompt(prompts.PROMPT_4, category, None, img)
        res5 = await run_prompt(prompts.PROMPT_5, category, None, img)

        return {
            "engine": "ai",
            "category": category,
            "rubric": res2["rubric"],
            "decision": res3,
            "health": res4["health"],
            "breed": res5["breed"]
        }
    except Exception as e:
        return {"error": str(e)}
