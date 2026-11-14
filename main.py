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
from ai_brain import ask_uje_router, generate_briefing, analyze_file_text, ask_gpt_free
from memory import init_db, save_fact, get_all_facts, save_pending, get_pending, clear_pending, clear_all_facts
from tools import (
    get_real_weather, get_taxi_link, get_auto_map_link, get_bus_map_link, get_walk_map_link,
    get_news_ufa, get_currency, get_traffic, current_zone, geocode_address, RESTAURANTS, ATTRACTIONS, HOTELS, APARTMENTS, DELIVERY_PLACES, DEMO_ROUTES, DEMO_INTEREST_ROUTES
)
from responses import RESPONSES, FACT_LABELS, DEFAULT_QUICK_ACTIONS, NAME_BLACKLIST, CITY_CORES, CITY_REACTIONS

import docx, PyPDF2, pandas as pd
load_dotenv()

ASSET_VERSION = "9.0"

MAP_POIS = [
    {"name": "Отель Азимут", "lat": 54.7431, "lon": 55.9721, "type": "hotel", "emoji": "🏨"},
    {"name": "Гостиница Башкирия", "lat": 54.7269, "lon": 55.9438, "type": "hotel", "emoji": "🏨"},
    {"name": "Ресторан «Башкирия»", "lat": 54.7267, "lon": 55.9500, "type": "food", "emoji": "🍽️"},
    {"name": "Terra Bashkiria", "lat": 54.7214, "lon": 55.9421, "type": "food", "emoji": "🍽️"},
    {"name": "Дом башкирской кухни", "lat": 54.7342, "lon": 55.9517, "type": "food", "emoji": "🍽️"},
    {"name": "Сойка", "lat": 54.7275, "lon": 55.9680, "type": "food", "emoji": "🍽️"},
    {"name": "Дом-музей Худайбердина", "lat": 54.7194, "lon": 55.9557, "type": "attraction", "emoji": "🏛️"},
    {"name": "Музей Боевой Славы", "lat": 54.8218, "lon": 56.0571, "type": "attraction", "emoji": "🏛️"},
    {"name": "Дом-музей Аксакова", "lat": 54.7135, "lon": 55.9516, "type": "attraction", "emoji": "🏛️"},
    {"name": "Музей истории Уфы", "lat": 54.7342, "lon": 55.9517, "type": "attraction", "emoji": "🏛️"},
    {"name": "Парк Кашкадан", "lat": 54.7722, "lon": 55.9483, "type": "attraction", "emoji": "🌳"},
    {"name": "Уфимское ожерелье", "lat": 54.7267, "lon": 55.9500, "type": "attraction", "emoji": "🌳"},
]

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

@app.post("/api/tts")
async def text_to_speech(req: TTSRequest):
    facts = get_all_facts()
    guide = facts.get("guide_gender", "female")
    voice = "filipp" if guide == "male" else "alena"

    clean_text = re.sub(r'[*#_~`®©]', '', re.sub(r'[\U00010000-\U0010ffff]', '', req.text)).strip()
    if not clean_text: return Response(status_code=400)
    folder_id, api_key = os.getenv("YC_FOLDER_ID"), os.getenv("YC_API_KEY")
    if not api_key or not folder_id: return Response(status_code=500)
    
    try:
        res = requests.post("https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize", headers={"Authorization": f"Api-Key {api_key}"}, data={"text": clean_text[:1000], "lang": "ru-RU", "voice": voice, "folderId": folder_id, "format": "mp3", "speed": "1.0"}, timeout=10)
        return Response(content=res.content, media_type="audio/mpeg") if res.status_code == 200 else Response(status_code=500)
    except: return Response(status_code=500)

@app.post("/api/location")
async def receive_location(data: LocationData):
    zone = current_zone(data.lat, data.lon)
    save_fact("current_location", f"{data.lat},{data.lon}")
    save_fact("current_zone", zone)
    
    pending = get_pending()
    if pending and pending.get("action") == "wait_geo":
        clear_pending()
        dest_data = pending.get("params")
        
        if ":" in dest_data:
            coords_str, dest_name = dest_data.split(":", 1)
            end_lat, end_lon = map(float, coords_str.split(","))
        else:
            dest_name = dest_data
            end_lat, end_lon = geocode_address(dest_name + ", Уфа")
        
        if end_lat:
            save_pending("wait_transport_choice", f"{end_lat},{end_lon}:{dest_name}")
            return {
                "status": "ok", "zone": zone, "action": "none", 
                "answer": f"Отлично, вижу тебя! Как поедем до {dest_name}?", 
                "buttons": [
                    {"label": "🚕 Такси", "action": f"[route:taxi:{end_lat},{end_lon}:{dest_name}]"},
                    {"label": "🚗 На авто", "action": f"[route:auto:{end_lat},{end_lon}:{dest_name}]"},
                    {"label": "🚌 Автобус", "action": f"[route:bus:{end_lat},{end_lon}:{dest_name}]"},
                    {"label": "🚶 Пешком", "action": f"[route:walk:{end_lat},{end_lon}:{dest_name}]"}
                ]
            }

    if pending and pending.get("action") == "wait_transport_choice":
        dest_name = pending.get("params")
        return {"status": "ok", "zone": zone, "action": "none", "answer": f"Отлично, вижу, что вы {zone}. На чем поедем до {dest_name}?", "buttons": [{"label": "🚕 Такси", "action": f"[transport:taxi:{dest_name}]"}, {"label": "🚌 Автобус", "action": f"[transport:bus:{dest_name}]"}, {"label": "🚶 Пешком", "action": "[transport:walk:{dest_name}]"}]}

    return {"status": "ok", "zone": zone, "action": "none", "answer": f"Отлично, вижу, что вы {zone}. Куда вам нужно построить маршрут? Назовите адрес или место, и я проложу путь."}

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

@app.post("/api/ask")
async def ask_bot(message: UserMessage):
    user_text = message.text.strip()
    text_lower = user_text.lower()
    facts = get_all_facts()
    transport = facts.get("transport", "неизвестно")

    if user_text == "[select_guide:female]":
        clear_all_facts()
        save_fact("guide_gender", "female")
        return {"answer": "Отличный выбор! Я рада приветствовать вас в нашей республике! Как к вам обращаться?", "action": "none", "quick_actions": []}
    
    if user_text == "[select_guide:male]":
        clear_all_facts()
        save_fact("guide_gender", "male")
        return {"answer": "Отличный выбор! Я рад приветствовать вас в нашей республике! Как к вам обращаться?", "action": "none", "quick_actions": []}

    # ✅ ИСПРАВЛЕННЫЙ SHOWCASE (БЕЛЫЙ ЗАМОК, САЛАВАТ И Т.Д.)
    if user_text.startswith("[showcase:"):
        key = user_text.replace("[showcase:", "").replace("]", "")
        name = ""
        if "salavat_flowers" in key or "salavat_close" in key:
            name = "Памятник Салавату Юлаеву"
            ans = "Памятник Салавату Юлаеву — самая крупная конная статуя в Европе. Это визитная карточка Уфы."
        elif "friendship" in key:
            name = "Монумент Дружбы"
            ans = "Монумент Дружбы — это гранитный обелиск высотой 35 метров."
        elif "castle" in key:
            name = "Белый Замок"
            ans = "Этот белоснежный замок — один из самых фотографируемых объектов Уфы."
        
        return {"answer": ans, "action": "none", "image": f"/static/img/showcase_{key}.jpg", "buttons": [
            {"label": "📍 Как доехать", "action": f"[route:walk:{name}]"},
            {"label": "📖 Подробнее", "action": "[attr_symbols]"}
        ]}

    # ✅ ОБРАБОТЧИК КАРТЫ (КОГДА НАЖИМАЮТ ТОЧКУ НА LEAFLET)
    if user_text.startswith("[map:"):
        place_name = user_text.replace("[map:", "").replace("]", "")
        return {"answer": f"Ты выбрал: {place_name}. Вот что я знаю об этом месте.", "action": "none", "buttons": [
            {"label": "📍 Как доехать", "action": f"[route:walk:{place_name}]"},
            {"label": "📖 Подробнее", "action": f"[details_attr:history:{place_name}]"}
        ]}

    if user_text.lower() == "хочу сюда":
        return {"answer": "Отлично! Выбери место из списка, и я проложу маршрут.", "action": "none"}

    # ✅ ОБРАБОТЧИК "ДАЛЬШЕ" ДЛЯ ПОШАГОВОГО ПРОВОДНИКА
    if user_text.lower() == "дальше":
        pending = get_pending()
        if pending and pending.get("action") == "guide_route":
            parts = pending.get("params").split("|")
            name = parts[0]
            mode = parts[1]
            step_idx = int(parts[2]) + 1
            
            route_data = DEMO_ROUTES.get(name)
            if route_data and mode in route_data:
                steps = route_data[mode]
                if step_idx < len(steps):
                    save_pending("guide_route", f"{name}|{mode}|{step_idx}")
                    return {"answer": f"Шаг {step_idx + 1}: {steps[step_idx]}\n\nНапиши 'Дальше', когда выполнишь.", "action": "none"}
                else:
                    clear_pending()
                    return {"answer": f"🎉 Поздравляю! Ты на месте — {name}. Приятного отдыха! Если что, я рядом.", "action": "none"}

    if user_text == "[route_interests_start]":
        return {"answer": "Отлично! Давай соберём твой идеальный день. Что тебе интереснее?", "action": "none", "buttons": [
            {"label": "🏛 История и музеи", "action": "[ri_interest:history]"},
            {"label": "🌳 Природа и прогулки", "action": "[ri_interest:nature]"},
            {"label": "🍽 Гастрономия", "action": "[ri_interest:food]"},
            {"label": "🚶 Всё сразу (микс)", "action": "[ri_interest:mix]"}
        ]}

    if user_text.startswith("[ri_interest:"):
        interest = user_text.replace("[ri_interest:", "").replace("]", "")
        save_fact("current_route_interest", interest)
        
        weather_data = get_real_weather("Уфа")
        is_bad_weather = False
        try:
            temp_str = weather_data.split('°')[0]
            temp = int(re.sub(r'[^\d-]', '', temp_str))
            if temp < 5 or "дождь" in weather_data.lower() or "снег" in weather_data.lower():
                is_bad_weather = True
        except: pass

        if is_bad_weather and interest in ["nature", "mix"]:
            return {"answer": f"Слушай, на улице сейчас {weather_data}. Для прогулок не очень. Давай я заменю природу на уютные места, чтобы не мёрзнуть?", "action": "none", "buttons": [
                {"label": "✅ Да, давай в тепло", "action": "[ri_agree_weather]"},
                {"label": "❄️ Нет, хочу гулять", "action": "[ri_force_weather]"}
            ]}

        route = DEMO_INTEREST_ROUTES.get(interest)
        if route:
            text = f"Вот твой маршрут: {route['title']}\n\n"
            for step in route["steps"]:
                text += f"{step['text']}\n\n"
            
            buttons = []
            for step in route["steps"]:
                name_part = step.get('place', step['text'].split('—')[1].split('(')[0].strip())
                buttons.append({"label": f"📖 {name_part}", "action": step['action']})
            
            first_place_name = route['steps'][0].get('place', route['steps'][0]['text'].split('—')[1].split('(')[0].strip())
            buttons.append({"label": "📍 Всё круто, веди меня", "action": f"[route:walk:{first_place_name}]"})
            
            return {"answer": text, "action": "none", "buttons": buttons}

    if user_text == "[ri_agree_weather]":
        save_fact("current_route_interest", "bad_weather_offer")
        route = DEMO_INTEREST_ROUTES["bad_weather_offer"]
        text = f"Отлично! Вот твой маршрут: {route['title']}\n\n" + "\n\n".join([s['text'] for s in route["steps"]])
        buttons = []
        for step in route["steps"]:
            name_part = step.get('place', step['text'].split('—')[1].split('(')[0].strip())
            buttons.append({"label": f"📖 {name_part}", "action": step['action']})
        first_place_name = route['steps'][0].get('place', route['steps'][0]['text'].split('—')[1].split('(')[0].strip())
        buttons.append({"label": "📍 Всё круто, веди меня", "action": f"[route:walk:{first_place_name}]"})
        return {"answer": text, "action": "none", "buttons": buttons}

    if user_text == "[ri_force_weather]":
        save_fact("current_route_interest", "nature")
        route = DEMO_INTEREST_ROUTES["nature"]
        text = f"Ну смотри, ты сам выбрал! Одевайся потеплее.\n\nВот твой маршрут: {route['title']}\n\n" + "\n\n".join([s['text'] for s in route["steps"]])
        buttons = []
        for step in route["steps"]:
            name_part = step.get('place', step['text'].split('—')[1].split('(')[0].strip())
            buttons.append({"label": f"📖 {name_part}", "action": step['action']})
        first_place_name = route['steps'][0].get('place', route['steps'][0]['text'].split('—')[1].split('(')[0].strip())
        buttons.append({"label": "📍 Всё круто, веди меня", "action": f"[route:walk:{first_place_name}]"})
        return {"answer": text, "action": "none", "buttons": buttons}

    if user_text.startswith("[ri_details:"):
        parts = user_text.replace("[ri_details:", "").replace("]", "").split(":", 1)
        category_key = parts[0] 
        place_name = parts[1]
        
        item = None
        is_rest = category_key.startswith("cat_")
        
        if is_rest:
            real_key = category_key.replace("cat_", "")
            item = next((i for i in RESTAURANTS.get(real_key, []) if i["name"] == place_name), None)
        else:
            real_key = category_key.replace("attr_", "")
            item = next((i for i in ATTRACTIONS.get(real_key, []) if i["name"] == place_name), None)

        if item:
            answer = f"**{item['name']}**\n\n{item['full_desc']}\n\n📍 {item['address']}\n🕒 {item['hours']}\n"
            if is_rest: answer += f"💰 Чек: {item['avg_check']}\n"
            else: answer += f"💰 {item['price']}\n"
            answer += f"⭐ Рейтинг: {item['rating']}"
            
            current_interest = facts.get("current_route_interest", "mix")
            route = DEMO_INTEREST_ROUTES.get(current_interest)
            
            buttons = []
            if route:
                for step in route["steps"]:
                    name_part = step.get('place', step['text'].split('—')[1].split('(')[0].strip())
                    buttons.append({"label": f"📖 {name_part}", "action": step['action']})
                
                first_place_name = route['steps'][0].get('place', route['steps'][0]['text'].split('—')[1].split('(')[0].strip())
                buttons.append({"label": "📍 Всё круто, веди меня", "action": f"[route:walk:{first_place_name}]"})
            
            return {"answer": answer, "action": "none", "image": item["image"], "buttons": buttons}

    if user_text == "[delivery_start]":
        return {"answer": "Отличный выбор! Что будем заказывать?", "action": "none", "buttons": [{"label": "🍕 Пицца", "action": "[delivery_pizza]"}, {"label": "🍣 Роллы", "action": "[delivery_sushi]"}, {"label": "🛒 Продукты", "action": "[delivery_grocery]"}]}
    if user_text.startswith("[delivery_"):
        key = user_text.replace("[delivery_", "").replace("]", "")
        place = DELIVERY_PLACES.get(key)
        if place: return {"answer": f"{place['text']}", "action": "show_card", "card": {"type": "food", "title": place["title"], "text": "Доставка до двери", "button": "Открыть сайт", "url": place["url"]}}

    if user_text == "[housing_start]":
        return {"answer": "Отлично! Выбирай, где остановиться:", "action": "none", "buttons": [{"label": "🏨 Отели", "action": "[housing_hotels]"}, {"label": "🏠 Квартиры посуточно", "action": "[housing_apartments]"}]}

    if user_text == "[housing_hotels]":
        cards = []
        for item in HOTELS:
            taxi_label = "🚗 На авто" if transport == "машина" else "🚕 Такси"
            action_type = "auto" if transport == "машина" else "taxi"
            cards.append({
                "title": item["name"],
                "desc": f"{item['desc']}\n📍 {item['address']}\n💰 {item['avg_check']}\n⭐ {item['rating']}",
                "image": item["image"],
                "buttons": [
                    {"label": "📖 Подробнее", "action": f"[details_hotel:{item['name']}]"},
                    {"label": taxi_label, "action": f"[route:{action_type}:{item['coords'][0]},{item['coords'][1]}:{item['name']}]"}
                ]
            })
        return {"answer": "Вот проверенные отели Уфы:", "action": "show_cards", "cards": cards, "buttons": [{"label": "🏨 Все отели", "action": "[housing_hotels]"}, {"label": "🏠 Квартиры", "action": "[housing_apartments]"}]}

    if user_text == "[housing_apartments]":
        cards = []
        for item in APARTMENTS:
            taxi_label = "🚗 На авто" if transport == "машина" else "🚕 Такси"
            action_type = "auto" if transport == "машина" else "taxi"
            cards.append({
                "title": item["name"],
                "desc": f"{item['desc']}\n📍 {item['address']}\n💰 {item['avg_check']}\n⭐ {item['rating']}",
                "image": item["image"],
                "buttons": [
                    {"label": "📞 Позвонить", "action": f"[call_phone:{item['phone']}]", "type": "url"},
                    {"label": "💬 WhatsApp", "action": f"https://wa.me/{item['phone'].replace('+','')}", "type": "url"},
                    {"label": taxi_label, "action": f"[route:{action_type}:{item['coords'][0]},{item['coords'][1]}:{item['name']}]"}
                ]
            })
        return {"answer": "Вот квартиры от хозяев:", "action": "show_cards", "cards": cards, "buttons": [{"label": "🏨 Отели", "action": "[housing_hotels]"}, {"label": "🏠 Все квартиры", "action": "[housing_apartments]"}]}

    if user_text.startswith("[call_phone:"):
        phone = user_text.replace("[call_phone:", "").replace("]", "")
        return {"answer": f"Набираю номер: {phone}", "action": "open_url", "url": f"tel:{phone}"}

    if user_text.startswith("[details_hotel:"):
        name = user_text.replace("[details_hotel:", "").replace("]", "")
        item = next((i for i in HOTELS if i["name"] == name), None)
        if item:
            taxi_label = "🚗 На авто" if transport == "машина" else "🚕 Такси"
            action_type = "auto" if transport == "машина" else "taxi"
            return {"answer": f"**{item['name']}**\n\n{item['full_desc']}\n\n📍 {item['address']}\n💰 {item['avg_check']}\n⭐ {item['rating']}", "action": "none", "image": item["image"], "buttons": [
                {"label": "📞 Позвонить", "action": f"[call_phone:{item['phone']}]", "type": "url"},
                {"label": taxi_label, "action": f"[route:{action_type}:{item['coords'][0]},{item['coords'][1]}:{item['name']}]"}
            ]}

    if user_text == "[food_start]":
        return {"answer": "Кушать подано! Что тебе сейчас по душе?", "action": "none", "buttons": [
            {"label": "🥘 Национальная", "action": "[cat_national]"}, 
            {"label": "☕ Кофе", "action": "[cat_coffee]"}, 
            {"label": "🍔 Бюджетно", "action": "[cat_budget]"}, 
            {"label": "🍷 Премиум", "action": "[cat_premium]"}, 
            {"label": "👨‍👩‍👧‍👦 С детьми", "action": "[cat_kids]"}
        ]}

    if user_text.startswith("[cat_"):
        key = user_text.replace("[cat_", "").replace("]", "")
        items = RESTAURANTS.get(key, [])
        if items:
            cards = []
            for item in items:
                taxi_label = "🚗 На авто" if transport == "машина" else "🚕 Такси"
                action_type = "auto" if transport == "машина" else "taxi"
                cards.append({
                    "title": item["name"],
                    "desc": f"{item['desc']}\n📍 {item['address']}\n🕒 {item['hours']}\n💰 Чек: {item['avg_check']}\n⭐ Рейтинг: {item['rating']}",
                    "image": item["image"],
                    "buttons": [
                        {"label": "📖 Подробнее", "action": f"[details_rest:{key}:{item['name']}]"},
                        {"label": taxi_label, "action": f"[route:{action_type}:{item['coords'][0]},{item['coords'][1]}:{item['name']}]"},
                        {"label": "🚌 Автобус", "action": f"[route:bus:{item['coords'][0]},{item['coords'][1]}:{item['name']}]"},
                        {"label": "🚶 Пешком", "action": f"[route:walk:{item['coords'][0]},{item['coords'][1]}:{item['name']}]"}
                    ]
                })
            
            nav_buttons = [
                {"label": "🥘 Национальная", "action": "[cat_national]"},
                {"label": "☕ Кофе", "action": "[cat_coffee]"},
                {"label": "🍔 Бюджетно", "action": "[cat_budget]"},
                {"label": "🍷 Премиум", "action": "[cat_premium]"},
                {"label": "👨‍👩‍👧‍👦 С детьми", "action": "[cat_kids]"}
            ]
            return {"answer": "Вот лучшие варианты:", "action": "show_cards", "cards": cards, "buttons": nav_buttons}

    if user_text.startswith("[attr_"):
        key = user_text.replace("[attr_", "").replace("]", "")
        items = ATTRACTIONS.get(key, [])
        if items:
            cards = []
            for item in items:
                taxi_label = "🚗 На авто" if transport == "машина" else "🚕 Такси"
                action_type = "auto" if transport == "машина" else "taxi"
                cards.append({
                    "title": item["name"],
                    "desc": f"{item['desc']}\n📍 {item['address']}\n🕒 {item['hours']}\n💰 {item['price']}\n⭐ Рейтинг: {item['rating']}",
                    "image": item["image"],
                    "buttons": [
                        {"label": "📖 Подробнее", "action": f"[details_attr:{key}:{item['name']}]"},
                        {"label": taxi_label, "action": f"[route:{action_type}:{item['coords'][0]},{item['coords'][1]}:{item['name']}]"},
                        {"label": "🚌 Автобус", "action": f"[route:bus:{item['coords'][0]},{item['coords'][1]}:{item['name']}]"},
                        {"label": "🚶 Пешком", "action": f"[route:walk:{item['coords'][0]},{item['coords'][1]}:{item['name']}]"}
                    ]
                })
            nav_buttons = [
                {"label": "🏛 История и музеи", "action": "[attr_history]"},
                {"label": "🌳 Природа и парки", "action": "[attr_nature]"},
                {"label": "🐎 Символы города", "action": "[attr_symbols]"}
            ]
            return {"answer": "Вот что стоит увидеть:", "action": "show_cards", "cards": cards, "buttons": nav_buttons}

    if user_text.startswith("[details_attr:"):
        parts = user_text.replace("[details_attr:", "").replace("]", "").split(":", 1)
        key, name = parts[0], parts[1]
        item = next((i for i in ATTRACTIONS.get(key, []) if i["name"] == name), None)
        if item:
            taxi_label = "🚗 На авто" if transport == "машина" else "🚕 Такси"
            action_type = "auto" if transport == "машина" else "taxi"
            return {"answer": f"**{item['name']}**\n\n{item['full_desc']}\n\n📍 {item['address']}\n🕒 {item['hours']}\n💰 {item['price']}\n⭐ Рейтинг: {item['rating']}", "action": "none", "image": item["image"], "buttons": [
                {"label": taxi_label, "action": f"[route:{action_type}:{item['coords'][0]},{item['coords'][1]}:{item['name']}]"},
                {"label": "🚌 Автобус", "action": f"[route:bus:{item['coords'][0]},{item['coords'][1]}:{item['name']}]"},
                {"label": "🚶 Пешком", "action": f"[route:walk:{item['coords'][0]},{item['coords'][1]}:{item['name']}]"}
            ]}

    if user_text.startswith("[details_rest:"):
        parts = user_text.replace("[details_rest:", "").replace("]", "").split(":", 1)
        key, name = parts[0], parts[1]
        item = next((i for i in RESTAURANTS.get(key, []) if i["name"] == name), None)
        if item:
            taxi_label = "🚗 На авто" if transport == "машина" else "🚕 Такси"
            action_type = "auto" if transport == "машина" else "taxi"
            return {"answer": f"**{item['name']}**\n\n{item['full_desc']}\n\n📍 {item['address']}\n🕒 {item['hours']}\n💰 Чек: {item['avg_check']}\n⭐ Рейтинг: {item['rating']}", "action": "none", "image": item["image"], "buttons": [
                {"label": taxi_label, "action": f"[route:{action_type}:{item['coords'][0]},{item['coords'][1]}:{item['name']}]"},
                {"label": "🚌 Автобус", "action": f"[route:bus:{item['coords'][0]},{item['coords'][1]}:{item['name']}]"},
                {"label": "🚶 Пешком", "action": f"[route:walk:{item['coords'][0]},{item['coords'][1]}:{item['name']}]"}
            ]}

    if user_text.startswith("[route:"):
        clear_pending()
        raw_parts = user_text.replace("[route:", "").replace("]", "").split(":", 2)
        mode = raw_parts[0]
        if len(raw_parts) == 3:
            coords = raw_parts[1].split(",")
            name = raw_parts[2]
        elif len(raw_parts) == 2:
            name = raw_parts[1]
            coords = None
        else:
            return {"answer": "Не понял маршрут", "action": "none"}

        if name == "Памятник Ленину перед Горсоветом":
            return {"answer": "Ты уже на месте! Памятник Ленину прямо перед тобой. Осмотрись и напиши 'Дальше'.", "action": "none"}

        route_data = DEMO_ROUTES.get(name)
        if route_data and mode in route_data:
            steps = route_data[mode]
            save_pending("guide_route", f"{name}|{mode}|0")
            return {"answer": f"Отлично, я поведу тебя за руку до {name}. Шаг 1: {steps[0]}\n\nНапиши 'Дальше', когда выполнишь.", "action": "none"}

        if mode in ["taxi", "auto"]:
            loc_str = facts.get("current_location", "")
            if not loc_str:
                if coords:
                    save_pending("wait_geo", f"{coords[0]},{coords[1]}:{name}")
                else:
                    save_pending("wait_geo", name)
                return {"answer": f"Чтобы построить маршрут до {name}, нажми на компас 🧭", "action": "none"}
            
            start_lat, start_lon = map(float, loc_str.split(','))
            if coords:
                end_lat, end_lon = float(coords[0]), float(coords[1])
            else:
                end_lat, end_lon = geocode_address(name + ", Уфа")

            if end_lat:
                if transport == "машина" or mode == "auto":
                    url = get_auto_map_link(start_lat, start_lon, end_lat, end_lon)
                    return {"answer": f"Автомаршрут до {name} построен.", "action": "show_card", "card": {"type": "map", "title": "🚗 На авто", "text": name, "button": "Открыть Карты", "url": url}}
                else:
                    url = get_taxi_link(start_lat, start_lon, end_lat, end_lon)
                    return {"answer": f"Маршрут до {name} построен.", "action": "show_card", "card": {"type": "taxi", "title": "🚕 Яндекс.Го", "text": name, "button": "Открыть Яндекс Go", "url": url}}
            return {"answer": "Не могу найти адрес.", "action": "none"}

        else: 
            loc_str = facts.get("current_location", "")
            if not loc_str:
                if coords:
                    save_pending("wait_geo", f"{coords[0]},{coords[1]}:{name}")
                else:
                    save_pending("wait_geo", name)
                return {"answer": "Сначала нажми на компас 🧭, чтобы я знал, откуда ехать.", "action": "none"}
            
            start_lat, start_lon = map(float, loc_str.split(','))
            if coords:
                end_lat, end_lon = float(coords[0]), float(coords[1])
            else:
                end_lat, end_lon = geocode_address(name + ", Уфа")

            if end_lat:
                if mode == "bus":
                    url = get_bus_map_link(start_lat, start_lon, end_lat, end_lon)
                    title = "🚌 Общественный транспорт"
                else:
                    url = get_walk_map_link(start_lat, start_lon, end_lat, end_lon)
                    title = "🚶 Пешеходный маршрут"
                    
                return {"answer": f"Маршрут до {name} построен. Открывай Яндекс.Карты.", "action": "show_card", "card": {"type": "map", "title": title, "text": name, "button": "Открыть Карты", "url": url}}
            return {"answer": "Не могу найти адрес.", "action": "none"}

    if user_text.startswith("[transport:"):
        parts = user_text.replace("[transport:", "").replace("]", "").split(":", 1)
        mode = parts[0]
        name = parts[1] if len(parts) > 1 else "Место"
        
        end_lat, end_lon = geocode_address(name + ", Уфа")
        
        if mode in ["taxi", "auto"] and end_lat:
            loc_str = facts.get("current_location", "")
            if not loc_str:
                save_pending("wait_geo", f"{end_lat},{end_lon}:{name}")
                return {"answer": f"Чтобы построить маршрут до {name}, нажми на компас 🧭", "action": "none"}
            start_lat, start_lon = map(float, loc_str.split(','))
            
            if transport == "машина" or mode == "auto":
                url = get_auto_map_link(start_lat, start_lon, end_lat, end_lon)
                return {"answer": f"Автомаршрут до {name} построен.", "action": "show_card", "card": {"type": "map", "title": "🚗 На авто", "text": name, "button": "Открыть Карты", "url": url}}
            else:
                url = get_taxi_link(start_lat, start_lon, end_lat, end_lon)
                return {"answer": f"Маршрут до {name} построен.", "action": "show_card", "card": {"type": "taxi", "title": "🚕 Яндекс.Го", "text": name, "button": "Открыть Яндекс Go", "url": url}}
        
        elif mode == "bus":
            route_data = DEMO_ROUTES.get(name)
            if route_data and "bus" in route_data:
                steps = route_data["bus"]
                save_pending("guide_route", f"{name}|bus|0")
                return {"answer": f"Отлично, я поведу тебя за руку до {name}. Шаг 1: {steps[0]}\n\nНапиши 'Дальше', когда выполнишь.", "action": "none"}
            else:
                if end_lat:
                    loc_str = facts.get("current_location", "")
                    if not loc_str:
                        save_pending("wait_geo", f"{end_lat},{end_lon}:{name}")
                        return {"answer": f"Чтобы построить маршрут до {name}, нажми на компас 🧭", "action": "none"}
                    start_lat, start_lon = map(float, loc_str.split(','))
                    url = get_bus_map_link(start_lat, start_lon, end_lat, end_lon)
                    return {"answer": f"Маршрут на автобусе до {name} построен. Открывай Яндекс.Карты.", "action": "show_card", "card": {"type": "map", "title": "🚌 Общественный транспорт", "text": name, "button": "Открыть Карты", "url": url}}
                return {"answer": "Не могу найти адрес. Попробуй иначе.", "action": "none"}
        
        elif mode == "walk":
            route_data = DEMO_ROUTES.get(name)
            if route_data and "walk" in route_data:
                steps = route_data["walk"]
                save_pending("guide_route", f"{name}|walk|0")
                return {"answer": f"Отлично, я поведу тебя за руку до {name}. Шаг 1: {steps[0]}\n\nНапиши 'Дальше', когда выполнишь.", "action": "none"}
            else:
                if end_lat:
                    loc_str = facts.get("current_location", "")
                    if not loc_str:
                        save_pending("wait_geo", f"{end_lat},{end_lon}:{name}")
                        return {"answer": f"Чтобы построить маршрут до {name}, нажми на компас 🧭", "action": "none"}
                    start_lat, start_lon = map(float, loc_str.split(','))
                    url = get_walk_map_link(start_lat, start_lon, end_lat, end_lon)
                    return {"answer": f"Пешеходный маршрут до {name} построен. Открывай Яндекс.Карты.", "action": "show_card", "card": {"type": "map", "title": "🚶 Пешком", "text": name, "button": "Открыть Карты", "url": url}}
                return {"answer": "Не могу найти адрес. Попробуй иначе.", "action": "none"}

    pending = get_pending()
    if pending and pending.get("action") == "wait_transport_choice":
        dest_data = pending.get("params")
        if ":" in dest_data:
            coords_str, dest_name = dest_data.split(":", 1)
        else:
            coords_str = None
            dest_name = dest_data

        mode = None
        if any(w in text_lower for w in ["такси", "машин", "авто", "го"]):
            mode = "auto" if transport == "машина" else "taxi"
        elif any(w in text_lower for w in ["автобус", "обществен", "маршрутк"]):
            mode = "bus"
        elif any(w in text_lower for w in ["пеш", "ногах", "идти", "пройти"]):
            mode = "walk"

        if mode:
            clear_pending()
            loc_str = facts.get("current_location", "")
            if not loc_str: return {"answer": "Нажми на компас 🧭", "action": "none"}
            
            start_lat, start_lon = map(float, loc_str.split(','))
            if coords_str:
                end_lat, end_lon = map(float, coords_str.split(','))
            else:
                end_lat, end_lon = geocode_address(dest_name + ", Уфа")

            if mode in ["taxi", "auto"]:
                if mode == "auto" or transport == "машина":
                    url = get_auto_map_link(start_lat, start_lon, end_lat, end_lon)
                    return {"answer": f"Автомаршрут до {dest_name} построен.", "action": "show_card", "card": {"type": "map", "title": "🚗 На авто", "text": dest_name, "button": "Открыть Карты", "url": url}}
                else:
                    url = get_taxi_link(start_lat, start_lon, end_lat, end_lon)
                    return {"answer": f"Маршрут до {dest_name} построен.", "action": "show_card", "card": {"type": "taxi", "title": "🚕 Яндекс.Го", "text": dest_name, "button": "Открыть Яндекс Go", "url": url}}
            elif mode == "bus":
                url = get_bus_map_link(start_lat, start_lon, end_lat, end_lon)
                return {"answer": f"Маршрут на автобусе до {dest_name} построен.", "action": "show_card", "card": {"type": "map", "title": "🚌 Общественный транспорт", "text": dest_name, "button": "Открыть Карты", "url": url}}
            elif mode == "walk":
                url = get_walk_map_link(start_lat, start_lon, end_lat, end_lon)
                return {"answer": f"Пешеходный маршрут до {dest_name} построен.", "action": "show_card", "card": {"type": "map", "title": "🚶 Пешком", "text": dest_name, "button": "Открыть Карты", "url": url}}
        else:
            btns = []
            if coords_str:
                btns = [
                    {"label": "🚕 Такси", "action": f"[route:taxi:{coords_str}:{dest_name}]"},
                    {"label": "🚗 На авто", "action": f"[route:auto:{coords_str}:{dest_name}]"},
                    {"label": "🚌 Автобус", "action": f"[route:bus:{coords_str}:{dest_name}]"},
                    {"label": "🚶 Пешком", "action": f"[route:walk:{coords_str}:{dest_name}]"}
                ]
            return {"answer": "Слушай, я не понял, как ты хочешь поехать. Выбери кнопку ниже или напиши 'такси', 'автобус' или 'пешком'.", "action": "none", "buttons": btns}

    if any(word in text_lower for word in ["поесть", "голоден", "ресторан", "кафе", "перекусить", "хочу есть", "кушать", "еда"]):
        return {"answer": "Кушать подано! Что тебе сейчас по душе?", "action": "none", "buttons": [{"label": "🥘 Национальная", "action": "[cat_national]"}, {"label": "☕ Кофе", "action": "[cat_coffee]"}, {"label": "🍔 Бюджетно", "action": "[cat_budget]"}, {"label": "🍷 Премиум", "action": "[cat_premium]"}, {"label": "👨‍👩‍👧‍👦 С детьми", "action": "[cat_kids]"}]}

    if any(word in text_lower for word in ["жить", "жилье", "жильё", "гостиниц", "отель", "квартир", "снять", "переночевать", "устал", "где поспать", "где остановиться"]):
        return {"answer": "Понял, тебе нужно жильё. Вот варианты:", "action": "none", "buttons": [{"label": "🏨 Отели", "action": "[housing_hotels]"}, {"label": "🏠 Квартиры посуточно", "action": "[housing_apartments]"}]}

    if any(word in text_lower for word in ["экскурси", "что посмотреть", "куда сходить", "куда съездить", "где погулять", "достопримечательности", "что есть в уфе", "чем заняться", "что еще", "расскажи про уфу", "хочу посмотреть"]):
        return {"answer": "У нас тут есть всё! А что тебе сейчас больше по душе?", "action": "none", "buttons": [{"label": "🏛 История и музеи", "action": "[attr_history]"}, {"label": "🌳 Природа и парки", "action": "[attr_nature]"}, {"label": "🐎 Символы города", "action": "[attr_symbols]"}]}

    if "name" not in facts or facts.get("name") == "":
        name_match = re.search(r'(?:меня зовут|зови меня|я)\s+([А-ЯЁ][а-яё]+)', user_text, re.IGNORECASE)
        if name_match: name = name_match.group(1).capitalize()
        else: name = user_text.split()[0].capitalize()
        
        if len(name) <= 30 and name.lower() not in NAME_BLACKLIST:
            save_fact("name", name)
            return {"answer": RESPONSES["onboarding_ask_city"].format(name=name), "action": "none"}
        return {"answer": "Слушай, напиши просто свое имя (например: Иван).", "action": "none"}

    if "from_city" not in facts or "transport" not in facts:
        city_lower = user_text.lower().strip()
        found_city = None
        city_match = re.search(r'(?:из|с|приехал из|прибыл из)\s+([А-ЯЁ][а-яё]+)', user_text, re.IGNORECASE)
        
        if city_match:
            found_city = city_match.group(1).lower()
        else:
            for core, canonical in CITY_CORES.items():
                if core in city_lower:
                    found_city = canonical
                    break
        
        if found_city:
            save_fact("from_city", found_city.capitalize())
            reaction = CITY_REACTIONS.get(found_city)
            if reaction:
                return {"answer": f"{reaction} А как вы до нас добрались? На поезде, на самолете, на машине или на автобусе?", "action": "none"}
            else:
                return {"answer": RESPONSES["onboarding_ask_transport"].format(city=found_city.capitalize()), "action": "none"}
        
        if "from_city" not in facts:
             return {"answer": "Слушай, а откуда ты к нам приехал? Назови город.", "action": "none"}

    if "transport" not in facts:
        if any(w in text_lower for w in ["поезд", "жд", "вокзал"]): new_transport = "поезд"
        elif any(w in text_lower for w in ["самолет", "аэропорт", "прилетел"]): new_transport = "самолет"
        elif any(w in text_lower for w in ["автобус"]): new_transport = "автобус" 
        elif any(w in text_lower for w in ["машин", "авто", "руле"]): new_transport = "машина"
        else: new_transport = "неизвестно"
        save_fact("transport", new_transport)
        return {"answer": RESPONSES["onboarding_ask_destination"], "action": "none"}

    if "home_address" not in facts:
        save_fact("home_address", user_text)
        transport = facts.get("transport", "неизвестно")
        care_msg = ""
        
        if transport == "машина": 
            care_msg = "По пути следования будет заправка Лукойл, советую заправиться, если бак пустой."
        elif transport == "поезд": 
            care_msg = "Кстати, рядом с вашим адресом есть круглосуточный магазин 'Купец', если проголодались."
        
        if transport == "машина":
            if not facts.get("current_location"):
                save_pending("wait_geo", user_text)
                return {"answer": f"Отлично, запомнила: {user_text}. {care_msg} Нажми на компас 🧭, чтобы я построила маршрут.", "action": "none"}
            
            loc = facts.get("current_location").split(',')
            end_lat, end_lon = geocode_address(user_text + ", Уфа")
            if end_lat:
                url = get_auto_map_link(float(loc[0]), float(loc[1]), end_lat, end_lon)
                return {"answer": f"Отлично! {care_msg} Автомаршрут до {user_text} построен.", "action": "show_card", "card": {"type": "map", "title": "🚗 На авто", "text": user_text, "button": "Открыть Карты", "url": url}}
            else:
                return {"answer": "Запомнила адрес, но не вижу тебя. Нажми на компас 🧭!", "action": "none"}
        else:
            save_pending("wait_transport_choice", user_text)
            return {"answer": f"Отлично, запомнила: {user_text}. {care_msg} А на чем поедем до отеля?", "action": "none", "buttons": [{"label": "🚕 Такси", "action": f"[transport:taxi:{user_text}]"}, {"label": "🚌 Автобус", "action": f"[transport:bus:{user_text}]"}, {"label": "🚶 Пешком", "action": f"[transport:walk:{user_text}]"}]}

    if any(word in text_lower for word in ["домой", "дом", "обратно", "в отель"]):
        loc_str = facts.get("current_location", "")
        if not loc_str: 
            save_pending("wait_geo", "домой")
            return {"answer": "Я не знаю, где ты. Нажми на компас 🧭, чтобы я нашла тебя.", "action": "none"}
        saved_addr = facts.get("home_address")
        if saved_addr:
            start_lat, start_lon = map(float, loc_str.split(','))
            end_lat, end_lon = geocode_address(saved_addr + ", Уфа")
            if end_lat:
                if transport == "машина":
                    url = get_auto_map_link(start_lat, start_lon, end_lat, end_lon)
                    return {"answer": f"Автомаршрут до дома построен.", "action": "show_card", "card": {"type": "map", "title": "🚗 На авто", "text": saved_addr, "button": "Открыть Карты", "url": url}}
                else:
                    url = get_taxi_link(start_lat, start_lon, end_lat, end_lon)
                    return {"answer": f"Маршрут до дома построен. Кстати, голодны? Могу заказать доставку прямо к двери.", "action": "show_card", "card": {"type": "taxi", "title": "🚕 Яндекс.Го", "text": saved_addr, "button": "Открыть Яндекс Go", "url": url}, "buttons": [{"label": "🍕 Заказать доставку", "action": "[delivery_start]"}]}
        save_pending("ask_home_address", "")
        return {"answer": "А где ты остановился? Назови отель или точный адрес.", "action": "none"}

    pending = get_pending()
    if pending and pending.get("action") == "ask_home_address":
        clear_pending()
        save_fact("home_address", user_text)
        loc_str = facts.get("current_location", "")
        if loc_str:
            start_lat, start_lon = map(float, loc_str.split(','))
            end_lat, end_lon = geocode_address(user_text + ", Уфа")
            if end_lat:
                if transport == "машина":
                    url = get_auto_map_link(start_lat, start_lon, end_lat, end_lon)
                    return {"answer": f"Отлично, запомнила: {user_text}. Автомаршрут построен!", "action": "show_card", "card": {"type": "map", "title": "🚗 На авто", "text": user_text, "button": "Открыть Карты", "url": url}}
                else:
                    url = get_taxi_link(start_lat, start_lon, end_lat, end_lon)
                    return {"answer": f"Отлично, запомнила: {user_text}. Маршрут построен!", "action": "show_card", "card": {"type": "taxi", "title": "🚕 Яндекс.Го", "text": user_text, "button": "Открыть Яндекс Go", "url": url}}
        return {"answer": "Адрес записала, но я не вижу, где ты. Нажми на компас 🧭!", "action": "none"}

    try:
        loop = asyncio.get_running_loop()
        intent = await loop.run_in_executor(executor, ask_uje_router, user_text, facts, message.history)
        for k, v in intent.get("new_facts", {}).items(): save_fact(k, v)
        
        if intent.get("action") == "call_taxi":
            dest = intent.get("params", {}).get("destination", "").strip()
            if dest:
                loc_str = facts.get("current_location", "")
                if not loc_str: 
                    save_pending("wait_geo", dest)
                    return {"answer": "Сначала нажми на компас 🧭, чтобы я знала, откуда ехать.", "action": "none"}
                start_lat, start_lon = map(float, loc_str.split(','))
                end_lat, end_lon = geocode_address(dest + ", Башкортостан")
                if end_lat:
                    if transport == "машина":
                        url = get_auto_map_link(start_lat, start_lon, end_lat, end_lon)
                        return {"answer": f"Автомаршрут построен: {dest}.", "action": "show_card", "card": {"type": "map", "title": "🚗 На авто", "text": dest, "button": "Открыть Карты", "url": url}}
                    else:
                        url = get_taxi_link(start_lat, start_lon, end_lat, end_lon)
                        return {"answer": f"Маршрут построен: {dest}.", "action": "show_card", "card": {"type": "taxi", "title": "🚕 Яндекс.Го", "text": dest, "button": "Открыть Яндекс Go", "url": url}}
            return {"answer": "Куда едем?", "action": "none"}
        
        return {"answer": intent.get("params", {}).get("reply", "Слушай, я немного задумалась. Давай еще раз?"), "action": "none"}
    except Exception as e:
        return {"answer": "У меня тут небольшие помехи. Давай еще раз попробуем?", "action": "none"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))