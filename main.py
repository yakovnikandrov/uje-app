# main.py
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import JSONResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict, Optional
import uvicorn
import asyncio
import io
import re
import random
import os
import requests
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from ai_brain import ask_uje_router, generate_briefing, analyze_file_text, ask_gpt_free
from memory import init_db, save_fact, get_all_facts, save_pending, get_pending, clear_pending
from tools import (
    get_real_weather, get_taxi_link, get_news_ufa, get_currency, get_traffic,
    current_zone, geocode_address, PROMO_PLACES, MAP_POIS
)
from responses import RESPONSES, FACT_LABELS, DEFAULT_QUICK_ACTIONS, NAME_BLACKLIST

import docx
import PyPDF2
import pandas as pd

load_dotenv()

# ✅ ВЕРСИЯ СТАТИКИ (меняй при каждом обновлении сайта)
ASSET_VERSION = "2.1"

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory="templates"), name="static")
templates = Jinja2Templates(directory="templates")
executor = ThreadPoolExecutor(max_workers=4)

class UserMessage(BaseModel):
    text: str
    history: Optional[List[Dict[str, str]]] = []

class LocationData(BaseModel):
    lat: float
    lon: float

class TTSRequest(BaseModel):
    text: str

# ✅ ОТДАЧА HTML С ЗАГОЛОВКАМИ NO-CACHE И ВЕРСИЕЙ
@app.get("/")
async def read_root(request: Request):
    response = templates.TemplateResponse(
        request=request, 
        name="index.html", 
        context={"asset_version": ASSET_VERSION}
    )
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.get("/manifest.json")
async def get_manifest():
    return JSONResponse({
        "name": "БАШГИД | Гид по Башкирии", "short_name": "БАШГИД", "start_url": "/",
        "display": "standalone", "background_color": "#005BBB", "theme_color": "#005BBB",
    }, headers={"Cache-Control": "no-cache"})

@app.get("/sw.js")
async def get_sw():
    sw_code = f"""
const CACHE_NAME = 'bashgid-v{ASSET_VERSION}';
self.addEventListener('install', (e) => {{ self.skipWaiting(); }});
self.addEventListener('activate', (e) => {{
    e.waitUntil(
        caches.keys().then((names) => Promise.all(
            names.filter((n) => n !== CACHE_NAME).map((n) => caches.delete(n))
        )).then(() => self.clients.claim())
    );
}});
self.addEventListener('fetch', (e) => {{
    e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
}});
"""
    return Response(content=sw_code, media_type="application/javascript", headers={"Cache-Control": "no-cache"})

@app.post("/api/tts")
async def text_to_speech(req: TTSRequest):
    text = req.text.strip()
    if not text: return Response(status_code=400)

    clean_text = re.sub(r'[\U00010000-\U0010ffff]', '', text)
    clean_text = re.sub(r'[*#_~`®©]', '', clean_text).strip()
    if not clean_text: return Response(status_code=400)

    folder_id = os.getenv("YC_FOLDER_ID")
    api_key = os.getenv("YC_API_KEY")
    
    if not api_key or not folder_id:
        return Response(status_code=500, content="API key or Folder ID missing")

    url = "https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize"
    headers = {"Authorization": f"Api-Key {api_key}"}
    data = {
        "text": clean_text[:1000],
        "lang": "ru-RU",
        "voice": "alena",
        "folderId": folder_id,
        "format": "mp3",
        "speed": "1.0"
    }

    try:
        response = requests.post(url, headers=headers, data=data, timeout=10)
        if response.status_code == 200:
            return Response(content=response.content, media_type="audio/mpeg")
        else:
            print(f"❌ Ошибка TTS: {response.status_code} - {response.text}")
            return Response(status_code=500)
    except Exception as e:
        print(f"❌ Ошибка запроса к TTS: {e}")
        return Response(status_code=500)

@app.post("/api/location")
async def receive_location(data: LocationData):
    zone = current_zone(data.lat, data.lon)
    save_fact("current_location", f"{data.lat},{data.lon}")
    save_fact("current_zone", zone)
    
    pending = get_pending()
    if pending and pending.get("action") == "wait_geo":
        clear_pending()
        dest_text = pending.get("params")
        
        start_lat, start_lon = data.lat, data.lon
        end_lat, end_lon = geocode_address(dest_text + ", Башкортостан")
        
        if end_lat:
            url = get_taxi_link(start_lat, start_lon, end_lat, end_lon)
            return {
                "status": "ok", 
                "zone": zone,
                "action": "show_card", 
                "answer": f"Отлично, вижу тебя! Маршрут до {dest_text} построен. Осталось нажать кнопку «Заказать».", 
                "card": {"type": "taxi", "title": "🚕 Яндекс.Го", "text": dest_text, "button": "Открыть Яндекс Go", "url": url}
            }
        else:
            return {"status": "ok", "zone": zone, "action": "none", "answer": f"Геолокация включена, но я не могу найти адрес «{dest_text}». Попробуй сказать иначе."}

    return {"status": "ok", "zone": zone}

@app.get("/api/current_weather")
async def get_current_weather():
    loop = asyncio.get_running_loop()
    weather = await loop.run_in_executor(executor, get_real_weather, "Уфа")
    parts = weather.split(',')
    temp = parts[0].strip() if parts else "--°"
    desc = parts[1].strip() if len(parts) > 1 else ""
    return {"temp": temp, "desc": desc}

@app.get("/api/map_points")
async def get_map_points():
    return {"points": MAP_POIS}

@app.get("/api/briefing")
async def get_briefing():
    loop = asyncio.get_running_loop()
    weather = await loop.run_in_executor(executor, get_real_weather, "Уфа")
    news = await loop.run_in_executor(executor, get_news_ufa)
    currency = await loop.run_in_executor(executor, get_currency)
    traffic = get_traffic()
    facts = get_all_facts()
    name = facts.get("name", "друг")
    text = await loop.run_in_executor(executor, generate_briefing, weather, traffic, currency, news, name)
    return {"answer": text}

@app.get("/api/status")
async def get_status():
    facts = get_all_facts()
    is_new = len(facts) == 0
    if is_new:
        greeting = RESPONSES["onboarding_hello"]
        placeholder = RESPONSES["input_placeholder_empty"]
    else:
        name = facts.get("name", "гость")
        greeting = RESPONSES["greeting_return"].format(name=name)
        placeholder = RESPONSES["input_placeholder_ready"]
    return {"is_new": is_new, "greeting": greeting, "placeholder": placeholder}

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    MAX_UPLOAD = 5 * 1024 * 1024
    raw = await file.read(MAX_UPLOAD + 1)
    if len(raw) > MAX_UPLOAD: return {"answer": "⚠️ Файл слишком большой (макс. 5 МБ).", "action": "none"}
    text_content = ""
    try:
        if file.filename.endswith(".docx"):
            doc = docx.Document(io.BytesIO(raw))
            text_content = "\n".join([para.text for para in doc.paragraphs])
        elif file.filename.endswith(".pdf"):
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(raw))
            for page in pdf_reader.pages: text_content += page.extract_text() + "\n"
        elif file.filename.endswith(".xlsx") or file.filename.endswith(".csv"):
            df = pd.read_excel(io.BytesIO(raw)) if file.filename.endswith(".xlsx") else pd.read_csv(io.BytesIO(raw))
            text_content = df.to_string()
        elif file.filename.endswith(".txt"):
            text_content = raw.decode("utf-8")
        else: return {"answer": "⚠️ Я пока не умею читать этот формат.", "action": "none"}
        
        loop = asyncio.get_running_loop()
        analysis = await loop.run_in_executor(executor, analyze_file_text, text_content, "гид", file.filename)
        return {"answer": analysis, "action": "none"}
    except Exception:
        return {"answer": "⚠️ Ошибка при чтении файла.", "action": "none"}

@app.post("/api/ask")
async def ask_bot(message: UserMessage):
    user_text = message.text.strip()
    text_lower = user_text.lower()
    history = message.history
    facts = get_all_facts()

    if user_text.startswith("[map:"):
        place_name = user_text.replace("[map:", "").replace("]", "")
        place = next((p for p in MAP_POIS if p["name"] == place_name), None)
        if place:
            if not facts.get("current_location"):
                save_pending("wait_geo", place_name)
                return {"answer": f"Отличный выбор! «{place_name}» — прекрасное место. Но чтобы вызвать такси, нажми на компас 🧭, чтобы я знал, откуда ехать.", "action": "none"}
            
            loc_str = facts.get("current_location")
            start_lat, start_lon = map(float, loc_str.split(','))
            end_lat, end_lon = place["lat"], place["lon"]
            url = get_taxi_link(start_lat, start_lon, end_lat, end_lon)
            return {"answer": f"Маршрут построен: {place_name}. В пути около {random.randint(20, 90)} минут. Осталось нажать кнопку.", "action": "show_card", "card": {"type": "taxi", "title": "🚕 Яндекс.Го", "text": place_name, "button": "Открыть Яндекс Go", "url": url}}

    if user_text.startswith("[promo:"):
        key = user_text.replace("[promo:", "").replace("]", "")
        place = PROMO_PLACES.get(key)
        if place:
            res = {"answer": place["short_text"], "action": "none", "image": place["image"]}
            res["buttons"] = [{"label": "Подробнее", "action": f"[promo_full:{key}]"}]
            return res
            
    if user_text.startswith("[promo_full:"):
        key = user_text.replace("[promo_full:", "").replace("]", "")
        place = PROMO_PLACES.get(key)
        if place:
            res = {"answer": place["full_text"], "action": "none", "image": place["image"]}
            return res

    if "name" not in facts:
        clean_text = user_text.strip()
        if len(clean_text) <= 30 and "?" not in clean_text:
            name = clean_text.split()[0].capitalize() 
            save_fact("name", name)
            return {"answer": RESPONSES["onboarding_ask_city"].format(name=name), "action": "none"}
        else:
            return {"answer": "Слушай, напиши просто свое имя (например: Иван).", "action": "none"}

    if "from_city" not in facts:
        city = user_text.capitalize()
        save_fact("from_city", city)
        return {"answer": RESPONSES["onboarding_welcome"].format(name=facts.get("name"), city=city), "action": "none"}

    pending = get_pending()
    if pending and pending.get("action") == "wait_geo":
        if "такси" not in text_lower and "автобус" not in text_lower:
            dest_text = pending.get("params")
            save_pending("wait_geo", dest_text)
            return {"answer": f"Я жду, когда ты нажмешь на компас 🧭, чтобы узнать, откуда ехать до «{dest_text}».", "action": "none"}

    if pending and pending.get("action") == "route_step_1":
        clear_pending()
        if "доехал" in text_lower or "на месте" in text_lower:
            return {"answer": "Огонь! Теперь аккуратно переходи дорогу на другую сторону и ищи остановку 167-го автобуса. Садись и едь до остановки «Гостиный двор». Давай, жду тебя на месте!", "action": "none"}
        else:
            save_pending("route_step_1", "")
            return {"answer": "Ты доехал до Центрального рынка? Напиши «Доехал», и я дам следующий шаг.", "action": "none"}

    if any(word in text_lower for word in ["домой", "дом", "обратно", "в отель"]):
        loc_str = facts.get("current_location", "")
        if not loc_str: 
            save_pending("wait_geo", "домой")
            return {"answer": "Я не знаю, где ты. Нажми на компас 🧭, чтобы я нашел тебя.", "action": "none"}
        
        saved_addr = facts.get("home_address")
        if saved_addr:
            start_lat, start_lon = map(float, loc_str.split(','))
            end_lat, end_lon = geocode_address(saved_addr + ", Уфа")
            if end_lat:
                url = get_taxi_link(start_lat, start_lon, end_lat, end_lon)
                return {"answer": f"Маршрут до дома построен: {saved_addr}. В пути около {random.randint(20, 90)} минут.", "action": "show_card", "card": {"type": "taxi", "title": "🚕 Яндекс.Го", "text": saved_addr, "button": "Открыть Яндекс Go", "url": url}}
            else:
                return {"answer": "Кажется, я не могу найти этот адрес на карте. Попробуй написать по-другому.", "action": "none"}
        else:
            save_pending("ask_home_address", "")
            return {"answer": "А где ты остановился? Назови отель или точный адрес (улица, дом).", "action": "none"}

    if pending and pending.get("action") == "ask_home_address":
        clear_pending()
        save_fact("home_address", user_text)
        loc_str = facts.get("current_location", "")
        if loc_str:
            start_lat, start_lon = map(float, loc_str.split(','))
            end_lat, end_lon = geocode_address(user_text + ", Уфа")
            if end_lat:
                url = get_taxi_link(start_lat, start_lon, end_lat, end_lon)
                return {"answer": f"Отлично, запомнил: {user_text}. Маршрут построен! В пути около {random.randint(20, 90)} минут.", "action": "show_card", "card": {"type": "taxi", "title": "🚕 Яндекс.Го", "text": user_text, "button": "Открыть Яндекс Go", "url": url}}
            else:
                return {"answer": "Кажется, я не могу найти этот адрес на карте. Попробуй написать по-другому.", "action": "none"}
        return {"answer": "Адрес записал, но я не вижу, где ты находишься. Нажми на компас 🧭!", "action": "none"}

    if "такси" in text_lower:
        if not facts.get("current_location"): 
            save_pending("wait_geo", "")
            return {"answer": "Я не знаю, где ты. Нажми на компас 🧭, чтобы я нашел тебя.", "action": "none"}
        
        dest_text = text_lower.replace("вызови", "").replace("такси", "").replace("до", "").replace("в", "").strip()
        
        if "стерлитамак" in dest_text or "терм" in dest_text:
            dest_text = "Термы Стерлитамак"
        elif not dest_text:
            save_pending("taxi_dest", "")
            return {"answer": "Куда едем? (Скажи «Домой», «В отель» или напиши адрес)", "action": "none"}

        loc_str = facts.get("current_location")
        start_lat, start_lon = map(float, loc_str.split(','))
        end_lat, end_lon = geocode_address(dest_text + ", Башкортостан")
        
        if end_lat:
            url = get_taxi_link(start_lat, start_lon, end_lat, end_lon)
            return {"answer": f"Маршрут построен: {dest_text}. В пути около {random.randint(20, 90)} минут.", "action": "show_card", "card": {"type": "taxi", "title": "🚕 Яндекс.Го", "text": dest_text, "button": "Открыть Яндекс Go", "url": url}}
        else:
            save_pending("taxi_dest", dest_text)
            return {"answer": f"Не могу найти «{dest_text}». Уточни адрес или напиши по-другому.", "action": "none"}

    YES = re.compile(r"^(да|давай|ок|окей|угу|ага|конечно|погнали|делай|го|хорошо)[.!\s]*$", re.I)
    if pending and pending.get("action") == "taxi_dest" and YES.match(user_text):
        clear_pending()
        loc_str = facts.get("current_location", "")
        if not loc_str: return {"answer": "Сначала нажми на компас 🧭, чтобы я знал, откуда ехать.", "action": "none"}
        
        dest_text = pending.get("params") or "Домой"
        start_lat, start_lon = map(float, loc_str.split(','))
        
        if dest_text == "Домой":
            saved_addr = facts.get("home_address")
            if saved_addr: end_lat, end_lon = geocode_address(saved_addr + ", Уфа"); dest_text = saved_addr
            else: return {"answer": "А где вы остановились? Назовите отель или адрес.", "action": "none"}
        else:
            end_lat, end_lon = geocode_address(dest_text + ", Башкортостан")
            if not end_lat: return {"answer": f"Не могу найти «{dest_text}». Проверь название.", "action": "none"}

        url = get_taxi_link(start_lat, start_lon, end_lat, end_lon)
        return {"answer": f"Маршрут построен: {dest_text}. В пути около {random.randint(20, 90)} минут.", "action": "show_card", "card": {"type": "taxi", "title": "🚕 Яндекс.Го", "text": dest_text, "button": "Открыть Яндекс Go", "url": url}}

    if "как добраться" in text_lower and "гостиный" in text_lower:
        save_pending("route_step_1", "")
        return {"answer": "О, отличный маршрут! Ты как, на такси хочешь с ветерком, или на автобусе прокатимся, как местные? Напиши «автобус» или «такси».", "action": "none"}
    
    if "автобус" in text_lower:
        save_pending("route_step_1", "")
        return {"answer": "Тогда слушай внимательно. Выходишь с вокзала, идёшь прямо до остановки «ЖД Вокзал». Твой 74-й автобус подъедет примерно через 15 минут. Запрыгивай и едь до остановки «Центральный рынок». Как доедешь — пиши «Доехал», я дам следующий шаг!", "action": "none"}

    try:
        loop = asyncio.get_running_loop()
        intent = await loop.run_in_executor(executor, ask_uje_router, user_text, facts, history)
        action = intent.get("action", "chat")
        params = intent.get("params", {})
        new_facts = intent.get("new_facts", {})

        for key, value in new_facts.items(): save_fact(key, value)

        if action == "call_taxi":
            destination = params.get("destination", "").strip()
            if destination:
                loc_str = facts.get("current_location", "")
                if not loc_str: 
                    save_pending("wait_geo", destination)
                    return {"answer": "Сначала нажми на компас 🧭, чтобы я знал, откуда ехать.", "action": "none"}
                
                start_lat, start_lon = map(float, loc_str.split(','))
                end_lat, end_lon = geocode_address(destination + ", Башкортостан")
                if end_lat:
                    url = get_taxi_link(start_lat, start_lon, end_lat, end_lon)
                    return {"answer": f"Маршрут построен: {destination}. В пути около {random.randint(20, 90)} минут.", "action": "show_card", "card": {"type": "taxi", "title": "🚕 Яндекс.Го", "text": destination, "button": "Открыть Яндекс Go", "url": url}}
                else:
                    save_pending("taxi_dest", destination)
                    return {"answer": f"Не могу найти «{destination}». Уточни адрес.", "action": "none"}
            save_pending("taxi_dest", "")
            return {"answer": "Куда едем?", "action": "none"}
        else:
            reply = params.get("reply") or "Слушай, я немного задумался. Давай еще раз?"
            return {"answer": reply, "action": "none"}

    except Exception as e:
        print(f"❌ Ошибка в /api/ask: {e}")
        return {"answer": "У меня тут небольшие помехи. Давай еще раз попробуем?", "action": "none"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)