# main.py
from fastapi import FastAPI, File, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from openai import AsyncOpenAI
import json
import os as osmod
import prompts

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

client = AsyncOpenAI()

async def run_prompt(prompt, input_data=None, image_bytes=None):
    if image_bytes:
        resp = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": "Analyze this image."}
            ],
            files=[{"name": "animal.jpg", "bytes": image_bytes}]
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
