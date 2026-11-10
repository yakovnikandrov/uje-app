from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse # НУЖНО ДЛЯ PWA
from pydantic import BaseModel
import uvicorn
import asyncio
from concurrent.futures import ThreadPoolExecutor
from ai_brain import ask_uje_router
from memory import init_db, save_fact, get_all_facts
from tools import get_weather, call_taxi, check_bus, play_music, order_food

app = FastAPI()
templates = Jinja2Templates(directory="templates")
executor = ThreadPoolExecutor(max_workers=4)

class UserMessage(BaseModel):
    text: str

class LocationData(BaseModel):
    lat: float
    lon: float

@app.on_event("startup")
async def startup():
    init_db()

@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={})

# --- PWA ЭНДПОИНТЫ ---
@app.get("/manifest.json")
async def get_manifest():
    return FileResponse("manifest.json")

@app.get("/sw.js")
async def get_sw():
    return FileResponse("sw.js")

@app.get("/api/promo")
async def get_promo():
    return {
        "active": True, 
        "image_url": "https://sun9-53.vkuserphoto.ru/s/v1/ig2/Iar_wLzl3QXGfVTTQgJ8s7WG-ealc62pd7qWf2b6BiplZXugbdkZM_z9rpOQ_NO3hpVywKFV8BR7xR77NfAGS3Z8.jpg?quality=95&as=32x32,48x48,72x72,108x108,160x160,240x240,360x360,480x480,540x540,640x640,720x720,1024x1024&from=bu&u=qVNf3at28_Nw0aHMXEsoOEBDtp-oLeT3Gw83_tJSTjo&cs=1024x0", 
        "text": "🔥 Закрытый гастроужин 15 ноября. Осталось 3 места! Жми на кнопку ниже."
    }

@app.post("/api/location")
async def receive_location(data: LocationData):
    save_fact("current_location", f"Координаты: {data.lat}, {data.lon}")
    print(f"📍 Получены координаты: {data.lat}, {data.lon}")
    return {"status": "ok"}

@app.post("/api/ask")
async def ask_bot(message: UserMessage):
    user_text = message.text.strip()
    print(f"📥 Получено: {user_text}") 
    
    KEY_NAMES = {
        "home_address": "🏠 Домашний адрес", "current_location": "📍 Локация",
        "favorite_coffee": "☕ Любимый кофе", "favorite_food": "🍔 Любимая еда",
        "job": "💼 Работа", "name": "👤 Имя", "city": "🏙 Город"
    }
    
    if "чем я лучше ии" in user_text.lower() or "моя мощь" in user_text.lower():
        reply = "🚀 **Чем я отличаюсь от ChatGPT?**\n\n🧠 **1. Я помню тебя.**\n🎯 **2. Я действую, а не советую.**\n🎙️ **3. Zero-UI (Голос в ушах).**\n\n**Итог:** ChatGPT — это библиотекарь. А я — твой личный Джарвис."
        return {"answer": reply, "action": "none"}

    if "расскажи кратко о себе" in user_text.lower():
        reply = "Отлично! 👤 Расскажи мне о себе всё в ОДНОМ сообщении (имя, город, работа, привычки). Я всё запомню!"
        return {"answer": reply, "action": "none"}

    if "посмотреть память" in user_text.lower():
        facts = get_all_facts()
        if not facts: return {"answer": "Память пустая. Нажми «Расскажи кратко о себе»!", "action": "none"}
        reply = "🧠 Вот что я помню:\n\n"
        for k, v in facts.items():
            reply += f"• {KEY_NAMES.get(k, k)}: {v}\n"
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

        if action == "get_weather":
            city = params.get("city", user_facts.get("city", "Уфа"))
            reply = await loop.run_in_executor(executor, get_weather, city)
            
        elif action == "call_taxi":
            dest = params.get("destination") or user_facts.get("home_address")
            pickup = user_facts.get("current_location", "Текущее местоположение")
            if not dest:
                reply = "🚕 Куда вызываем такси? Я пока не знаю ваш адрес."
            else:
                reply = await loop.run_in_executor(executor, call_taxi, pickup, dest)
                
        elif action == "check_bus":
            stop = user_facts.get("current_location", "Остановка")
            reply = await loop.run_in_executor(executor, check_bus, stop)
            
        elif action == "play_music":
            genre = params.get("genre", "музыку")
            reply = await loop.run_in_executor(executor, play_music, genre)
            return {"answer": reply, "action": "show_player"}
            
        elif action == "order_food":
            dish = params.get("dish", "еду")
            reply = await loop.run_in_executor(executor, order_food, dish)
            
        else:
            reply = params.get("reply", "Я вас услышал.")

        return {"answer": reply, "action": "none"}

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return {"answer": f"⚠️ Ошибка на сервере: {e}", "action": "none"}

if __name__ == "__main__":
    print("🚀 Сервер УЖЕ запущен!")
    uvicorn.run(app, host="127.0.0.1", port=8000)