# main.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from ai_brain import ask_uje_router, generate_briefing
from memory import init_db, save_fact, get_all_facts
from tools import get_real_weather, get_taxi_link, get_news_ufa, get_currency, get_traffic
from responses import RESPONSES, FACT_LABELS

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory="templates")
executor = ThreadPoolExecutor(max_workers=4)

class UserMessage(BaseModel):
    text: str

class LocationData(BaseModel):
    lat: float
    lon: float

@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={})

@app.get("/manifest.json")
async def get_manifest():
    return JSONResponse({
        "name": "УЖЕ | Дворецкий", "short_name": "УЖЕ", "start_url": "/",
        "display": "standalone", "background_color": "#0f0f0f", "theme_color": "#0f0f0f",
        "icons": [{"src": "https://placehold.co/192x192/00c853/000000?text=UJE", "sizes": "192x192", "type": "image/png"}]
    })

@app.get("/sw.js")
async def get_sw():
    return "self.addEventListener('install', (e) => {}); self.addEventListener('fetch', (e) => {});"

@app.post("/api/location")
async def receive_location(data: LocationData):
    save_fact("current_location", f"{data.lat},{data.lon}")
    print(f"📍 Получены координаты: {data.lat}, {data.lon}")
    return {"status": "ok"}

@app.get("/api/briefing")
async def get_briefing():
    loop = asyncio.get_running_loop()
    
    weather = await loop.run_in_executor(executor, get_real_weather, "Уфа")
    news = await loop.run_in_executor(executor, get_news_ufa)
    currency = await loop.run_in_executor(executor, get_currency)
    traffic = get_traffic()
    
    facts = get_all_facts()
    name = facts.get("name", "Яков")
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
        name = facts.get("name", "друг")
        greeting = RESPONSES["greeting_return"].format(name=name)
        placeholder = RESPONSES["input_placeholder_ready"]
    return {"is_new": is_new, "greeting": greeting, "placeholder": placeholder}

@app.post("/api/ask")
async def ask_bot(message: UserMessage):
    user_text = message.text.strip()
    if "что в разработке" in user_text.lower():
        return {"answer": "🚀 Скоро в УЖЕ: Такси, Доставка еды, Карты, Свой плеер, GPS-трекер. Я расту!", "action": "none"}
    if "чем я лучше ии" in user_text.lower() or "моя мощь" in user_text.lower():
        return {"answer": RESPONSES["manifesto"], "action": "none"}
    if "посмотреть память" in user_text.lower():
        facts = get_all_facts()
        if not facts: return {"answer": RESPONSES["memory_empty"], "action": "none"}
        reply = RESPONSES["memory_header"] + "\n".join([f"• {FACT_LABELS.get(k, k)}: {v}" for k, v in facts.items()])
        return {"answer": reply, "action": "none"}

    try:
        user_facts = get_all_facts()
        loop = asyncio.get_running_loop()
        intent = await loop.run_in_executor(executor, ask_uje_router, user_text, user_facts)
        
        action = intent.get("action", "chat")
        params = intent.get("params", {})
        new_facts = intent.get("new_facts", {})
        
        for key, value in new_facts.items():
            save_fact(key, value)

        if action == "save_fact":
            if "name" in new_facts:
                reply = RESPONSES["onboarding_got_name"].format(name=str(new_facts["name"]).capitalize())
            elif "commute_type" in new_facts:
                ctype = new_facts["commute_type"].lower()
                if "такси" in ctype: reply = RESPONSES["onboarding_taxi_home"]
                elif "автобус" in ctype: reply = RESPONSES["onboarding_bus_num"]
                elif "машин" in ctype: reply = RESPONSES["onboarding_car_model"]
                else: reply = RESPONSES["onboarding_finish"] 
            elif "home_address" in new_facts: reply = RESPONSES["onboarding_taxi_work"]
            elif "work_address" in new_facts or "bus_number" in new_facts or "car_model" in new_facts: reply = RESPONSES["onboarding_finish"]
            elif "phone_mom" in new_facts: reply = "Записал номер мамы."
            elif "phone_dad" in new_facts: reply = "Записал номер папы."
            else: reply = RESPONSES["save_fact_ok"]
                
        elif action == "get_weather":
            reply = await loop.run_in_executor(executor, get_real_weather, "Уфа")
            reply = f"В Уфе сейчас {reply}. Одевайся по погоде."
            
        elif action == "call_taxi":
            dest = params.get("destination") or user_facts.get("home_address") if "домой" in user_text.lower() else user_facts.get("work_address")
            if not dest: reply = "Куда едем? Скажи адрес."
            else:
                loc_str = user_facts.get("current_location", "")
                if loc_str:
                    lat, lon = map(float, loc_str.split(','))
                    return {"answer": f"Маршрут: от тебя -> {dest}", "action": "show_taxi_btn", "url": get_taxi_link(lat, lon, dest)}
                else: reply = "Нажми на компас 🧭, чтобы я построил маршрут."

        elif action == "call_contact":
            name_key = params.get("name", "").lower()
            if "мам" in name_key: name_key = "mom"
            elif "пап" in name_key: name_key = "dad"
            phone = user_facts.get(f"phone_{name_key}")
            if phone: return {"answer": f"Набираю...", "action": "show_call_btn", "phone": phone}
            else: reply = f"Я не знаю номер. Скажи: «Запиши {name_key} 8-999-123-45-67»."

        else: 
            reply = params.get("reply") or params.get("text") or "Я вас услышал."

        return {"answer": reply, "action": "none"}

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return {"answer": RESPONSES["error"], "action": "none"}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)