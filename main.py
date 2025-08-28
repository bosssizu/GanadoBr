# main.py
from fastapi import FastAPI, File, UploadFile
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

async def run_prompt(prompt, input_data=None, image_bytes=None):
    if image_bytes:
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        resp = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": [
                    {"type": "text", "text": "Analyze this image."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                ]}
            ]
        )
    else:
        resp = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(input_data)}
            ]
        )
    return json.loads(resp.choices[0].message.content)

@app.get("/")
async def root():
    return FileResponse(osmod.path.join("static", "index.html"))

@app.post("/api/evaluate")
async def evaluate(file: UploadFile = File(...)):
    try:
        img = await file.read()

        res1 = await run_prompt(prompts.PROMPT_1, None, img)
        res2 = await run_prompt(prompts.PROMPT_2, res1)
        res3 = await run_prompt(prompts.PROMPT_3, res2)
        res4 = await run_prompt(prompts.PROMPT_4, None, img)
        res5 = await run_prompt(prompts.PROMPT_5, None, img)

        return {
            "engine": "ai",
            "rubric": res2["rubric"],
            "decision": res3,
            "health": res4["health"],
            "breed": res5["breed"]
        }
    except Exception as e:
        return {"error": str(e)}
