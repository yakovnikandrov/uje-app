# main.py
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import JSONResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict, Optional
import uvicorn, asyncio, io, re, random, os, requests
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from routers.chat import router as chat_router

from ai_brain import ask_uje_router, generate_briefing, analyze_file_text, ask_gpt_free
from memory import init_db, save_fact, get_all_facts, save_pending, get_pending, clear_pending, clear_all_facts
from tools import (
    get_real_weather, get_taxi_link, get_auto_map_link, get_bus_map_link, get_walk_map_link,
    get_news_ufa, get_currency, get_traffic, current_zone, geocode_address, RESTAURANTS, ATTRACTIONS, HOTELS, APARTMENTS, DELIVERY_PLACES, DEMO_ROUTES, DEMO_INTEREST_ROUTES
)
from responses import RESPONSES, FACT_LABELS, DEFAULT_QUICK_ACTIONS, NAME_BLACKLIST, CITY_CORES, CITY_REACTIONS

# ✅ НОВЫЕ ИМПОРТЫ ИЗ ПАПОК (которые мы создали)
from data.config import ASSET_VERSION
from data.places import MAP_POIS
from routers.tts import router as tts_router
from routers.location import router as location_router

import docx, PyPDF2, pandas as pd
load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(lifespan=lifespan)
app.include_router(location_router)
app.include_router(chat_router)
app.mount("/static", StaticFiles(directory="templates"), name="static")
templates = Jinja2Templates(directory="templates")
executor = ThreadPoolExecutor(max_workers=4)

# ✅ ПОДКЛЮЧАЕМ РОУТЕР TTS
app.include_router(tts_router)

@app.get("/")
async def read_root(request: Request):
    response = templates.TemplateResponse(request=request, name="index.html", context={"asset_version": ASSET_VERSION})
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response

@app.get("/manifest.json")
async def get_manifest():
    return JSONResponse({"name": "БАШГИД", "short_name": "БАШГИД", "start_url": "/", "display": "standalone", "background_color": "#005BBB", "theme_color": "#005BBB"}, headers={"Cache-Control": "no-cache"})

@app.get("/sw.js")
async def get_sw():
    return Response(content=f"const CACHE_NAME = 'bashgid-v{ASSET_VERSION}';\nself.addEventListener('install', (e) => {{ self.skipWaiting(); }});\nself.addEventListener('activate', (e) => {{ e.waitUntil(caches.keys().then((names) => Promise.all(names.filter((n) => n !== CACHE_NAME).map((n) => caches.delete(n)))).then(() => self.clients.claim())); }});\nself.addEventListener('fetch', (e) => {{ e.respondWith(fetch(e.request).catch(() => caches.match(e.request))); }});", media_type="application/javascript", headers={"Cache-Control": "no-cache"})

@app.post("/api/reset")
async def reset_memory():
    clear_all_facts()
    return {"status": "ok"}

@app.get("/api/current_weather")
async def get_current_weather():
    parts = (await asyncio.get_running_loop().run_in_executor(executor, get_real_weather, "Уфа")).split(',')
    return {"temp": parts[0].strip() if parts else "--°", "desc": parts[1].strip() if len(parts) > 1 else ""}

@app.get("/api/map_points")
async def get_map_points(): return {"points": MAP_POIS}

@app.get("/api/briefing")
async def get_briefing():
    loop = asyncio.get_running_loop()
    w = await loop.run_in_executor(executor, get_real_weather, "Уфа")
    n = await loop.run_in_executor(executor, get_news_ufa)
    c = await loop.run_in_executor(executor, get_currency)
    t = get_traffic()
    facts = get_all_facts()
    text = await loop.run_in_executor(executor, generate_briefing, w, t, c, n, facts.get("name", "друг"))
    return {"answer": text}

@app.get("/api/status")
async def get_status():
    facts = get_all_facts()
    is_new = len(facts) == 0 or "guide_gender" not in facts
    if is_new:
        return {
            "is_new": True, 
            "greeting": "Привет! Я — БашГид, ваш персональный гид по Башкирии. Выбери, с кем продолжишь путь:", 
            "action": "select_guide",
            "placeholder": RESPONSES["input_placeholder_empty"]
        }
    return {"is_new": False, "greeting": RESPONSES["greeting_return"].format(name=facts.get("name", "гость")), "placeholder": RESPONSES["input_placeholder_ready"], "quick_actions": DEFAULT_QUICK_ACTIONS}

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    raw = await file.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024: return {"answer": "⚠️ Файл слишком большой.", "action": "none"}
    text = ""
    try:
        if file.filename.endswith(".docx"): text = "\n".join([p.text for p in docx.Document(io.BytesIO(raw)).paragraphs])
        elif file.filename.endswith(".pdf"): text = "\n".join([p.extract_text() for p in PyPDF2.PdfReader(io.BytesIO(raw)).pages])
        elif file.filename.endswith(".xlsx") or file.filename.endswith(".csv"): text = (pd.read_excel(io.BytesIO(raw)) if file.filename.endswith(".xlsx") else pd.read_csv(io.BytesIO(raw))).to_string()
        elif file.filename.endswith(".txt"): text = raw.decode("utf-8")
        else: return {"answer": "⚠️ Я пока не умею читать этот формат.", "action": "none"}
        analysis = await asyncio.get_running_loop().run_in_executor(executor, analyze_file_text, text, "гид", file.filename)
        return {"answer": analysis, "action": "none"}
    except: return {"answer": "⚠️ Ошибка при чтении файла.", "action": "none"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))