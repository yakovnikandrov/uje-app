# main.py
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Dict, Optional
import uvicorn
import asyncio
import io
import re
import random
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from ai_brain import ask_uje_router, generate_briefing, analyze_file_text, ask_gpt_free
from memory import init_db, save_fact, get_all_facts, save_pending, get_pending, clear_pending
from tools import (
    get_real_weather, get_taxi_link, get_news_ufa, get_currency, get_traffic,
    get_full_route_home, current_zone, geocode_address, PROMO_PLACES, MAP_POIS
)
from responses import RESPONSES, FACT_LABELS, DEFAULT_QUICK_ACTIONS, NAME_BLACKLIST

import docx
import PyPDF2
import pandas as pd

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory="templates")
executor = ThreadPoolExecutor(max_workers=4)

class UserMessage(BaseModel):
    text: str
    history: Optional[List[Dict[str, str]]] = []

class LocationData(BaseModel):
    lat: float
    lon: float

@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={})

@app.get("/manifest.json")
async def get_manifest():
    return JSONResponse({
        "name": "БАШГИД | Гид по Башкирии", "short_name": "БАШГИД", "start_url": "/",
        "display": "standalone", "background_color": "#005BBB", "theme_color": "#005BBB",
    })

@app.get("/sw.js")
async def get_sw():
    return "self.addEventListener('install', (e) => {}); self.addEventListener('fetch', (e) => {});"

@app.post("/api/location")
async def receive_location(data: LocationData):
    zone = current_zone(data.lat, data.lon)
    save_fact("current_location", f"{data.lat},{data.lon}")
    save_fact("current_zone", zone)
    return {"status": "ok", "zone": zone}

@app.get("/api/current_weather")
async def get_current_weather():
    loop = asyncio.get_running_loop()
    weather = await loop.run_in_executor(executor, get_real_weather, "Уфа")
    parts = weather.split(',')
    temp = parts[0].strip() if parts else "--°"
    desc = parts[1].strip() if len(parts) > 1 else ""
    return {"temp": temp, "desc": desc}

# ✅ НОВОЕ: Эндпоинт для получения точек на карте
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
    history = message.history
    facts = get_all_facts()

    # ✅ НОВОЕ: Обработка клика с карты "Хочу сюда"
    if user_text.startswith("[map:"):
        place_name = user_text.replace("[map:", "").replace("]", "")
        # Ищем место в базе
        place = next((p for p in MAP_POIS if p["name"] == place_name), None)
        if place:
            if not facts.get("current_location"):
                return {"answer": f"Отличный выбор! «{place_name}» — прекрасное место. Но чтобы вызвать такси, нажми на компас 🧭, чтобы я знал, откуда ехать.", "action": "none"}
            
            # Сохраняем как ожидание такси
            save_pending("taxi_dest", place_name)
            return {"answer": f"Отличный выбор! «{place_name}» — прекрасное место. Вызываем такси до него? Нажми «Да» для подтверждения.", "action": "none"}

    # ✅ 0. ОБРАБОТКА РЕКЛАМНЫХ КНОПОК
    if user_text.startswith("[promo:"):
        key = user_text.replace("[promo:", "").replace("]", "")
        place = PROMO_PLACES.get(key)
        if place:
            res = {"answer": place["text"], "action": "none"}
            if place.get("image"): res["image"] = place["image"]
            return res

    # ✅ 1. ЖЕЛЕЗОБЕТОННЫЙ ОНБОРДИНГ
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

    # ========================================================
    # 2. РЕЖИМ "ПРОВОДНИК" (Ждем "Доехал")
    # ========================================================
    pending = get_pending()
    if pending and pending.get("action") == "route_step_1":
        clear_pending()
        if "доехал" in user_text.lower() or "на месте" in user_text.lower():
            return {"answer": "Огонь! Теперь аккуратно переходи дорогу на другую сторону и ищи остановку 167-го автобуса. Садись и едь до остановки «Гостиный двор». Давай, жду тебя на месте!", "action": "none"}
        else:
            save_pending("route_step_1", "")
            return {"answer": "Ты доехал до Центрального рынка? Напиши «Доехал», и я дам следующий шаг.", "action": "none"}

    # ========================================================
    # 3. ОБРАБОТКА ТАКСИ
    # ========================================================
    YES = re.compile(r"^(да|давай|ок|окей|угу|ага|конечно|погнали|делай|го|хорошо)[.!\s]*$", re.I)
    if pending and pending.get("action") == "taxi_dest":
        clear_pending()
        loc_str = facts.get("current_location", "")
        if not loc_str: return {"answer": "Сначала нажми на компас 🧭, чтобы я знал, откуда ехать.", "action": "none"}
        
        start_lat, start_lon = map(float, loc_str.split(','))
        dest_text = user_text.strip()
        if YES.match(dest_text) and pending.get("params"): dest_text = pending["params"]
        
        if any(word in dest_text.lower() for word in ["дом", "отель", "гостиниц", "хостел"]):
            saved_addr = facts.get("home_address")
            if saved_addr: end_lat, end_lon = geocode_address(saved_addr + ", Уфа"); dest_text = saved_addr
            else: return {"answer": "А где вы остановились? Назовите отель или адрес.", "action": "none"}
        else:
            end_lat, end_lon = geocode_address(dest_text + ", Башкортостан")
            if not end_lat: return {"answer": f"Не могу найти «{dest_text}». Проверьте название.", "action": "none"}

        url = get_taxi_link(start_lat, start_lon, end_lat, end_lon)
        return {"answer": f"Маршрут построен: {dest_text}. В пути около {random.randint(20, 90)} минут. Осталось нажать кнопку.", "action": "show_card", "card": {"type": "taxi", "title": "🚕 Яндекс.Го", "text": dest_text, "button": "Открыть Яндекс Go", "url": url}}

    if "такси" in user_text.lower():
        if not facts.get("current_location"): return {"answer": "Я не знаю, где ты. Нажми на компас 🧭, чтобы я нашел тебя.", "action": "none"}
        if "стерлитамак" in user_text.lower() or "терм" in user_text.lower():
            save_pending("taxi_dest", "Термы Стерлитамак")
            return {"answer": "Такси до Терм Стерлитамак? Это далеко (около 1,5 часов). Если готовы — нажмите «Да» или напишите другой адрес.", "action": "none"}
        save_pending("taxi_dest", "")
        return {"answer": "Куда едем? (Скажи «Домой», «В отель» или напиши адрес)", "action": "none"}

    # ✅ ПРИМЕР МАРШРУТА "ПРОВОДНИК"
    if "как добраться" in user_text.lower() and "гостиный" in user_text.lower():
        save_pending("route_step_1", "")
        return {"answer": "О, отличный маршрут! Ты как, на такси хочешь с ветерком, или на автобусе прокатимся, как местные? Напиши «автобус» или «такси».", "action": "none"}
    
    if "автобус" in user_text.lower():
        save_pending("route_step_1", "")
        return {"answer": "Тогда слушай внимательно. Выходишь с вокзала, идёшь прямо до остановки «ЖД Вокзал». Твой 74-й автобус подъедет примерно через 15 минут. Запрыгивай и едь до остановки «Центральный рынок». Как доедешь — пиши «Доехал», я дам следующий шаг!", "action": "none"}

    # ========================================================
    # 4. УМНЫЙ ИИ
    # ========================================================
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
                save_pending("taxi_dest", destination)
                return {"answer": f"Такси до «{destination}»? Нажмите «Да» для подтверждения.", "action": "none"}
            save_pending("taxi_dest", "")
            return {"answer": "Куда едем?", "action": "none"}
        else:
            reply = params.get("reply") or "Слушай, я немного задумался. Давай еще раз?"
            return {"answer": reply, "action": "none"}

    except Exception as e:
        print(f"❌ Ошибка в /api/ask: {e}")
        return {"answer": "У меня тут небольшие помехи. Давай еще раз попробуем?", "action": "none"}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)