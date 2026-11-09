import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn
import asyncio
from concurrent.futures import ThreadPoolExecutor
from ai_brain import ask_uje_router
from memory import init_db, save_fact, get_all_facts

app = FastAPI()

# СОЗДАЕМ ПАПКУ STATIC, ЕСЛИ ЕЁ НЕТ
os.makedirs("static", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

executor = ThreadPoolExecutor(max_workers=4)

class UserMessage(BaseModel):
    text: str

@app.on_event("startup")
async def startup():
    init_db()

@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={})

@app.post("/api/ask")
async def ask_bot(message: UserMessage):
    user_text = message.text.strip().lower()
    print(f"📥 Получено: {user_text}") 
    
    KEY_NAMES = {
        "home_address": "🏠 Домашний адрес",
        "work_address": "🏢 Рабочий адрес",
        "favorite_coffee": "☕ Любимый кофе",
        "favorite_food": "🍔 Любимая еда"
    }
    
    if "что ты обо мне знаешь" in user_text or "моя память" in user_text:
        facts = get_all_facts()
        if not facts:
            return {"answer": "Я пока ничего о тебе не знаю. Скажи, где ты живешь или что любишь."}
        
        reply = "🧠 Вот что я о тебе помню:\n\n"
        for k, v in facts.items():
            ru_key = KEY_NAMES.get(k, k)
            reply += f"• {ru_key}: {v}\n"
        return {"answer": reply}
    
    try:
        user_facts = get_all_facts()
        loop = asyncio.get_running_loop()
        intent = await loop.run_in_executor(executor, ask_uje_router, message.text, user_facts)
        
        action = intent.get("action")
        params = intent.get("params", {})
        new_facts = intent.get("new_facts", {})
        
        print(f"🧠 ИИ решил: {action} | Параметры: {params} | Новые факты: {new_facts}")

        for key, value in new_facts.items():
            save_fact(key, value)
            print(f"💾 Запомнил: {key} = {value}")

        if action == "help":
            reply = (
                "Я — твой цифровой дворецкий. Вот что я умею:\n\n"
                "🚕 Транспорт: Вызову такси (просто скажи 'Вызови такси домой').\n"
                "🍔 Еда: Найду и закажу еду (скажи 'Хочу мой обычный кофе').\n"
                "🎭 Досуг: Найду афишу.\n\n"
                "Я запоминаю твои привычки, чтобы делать всё за 1 клик!"
            )
        elif action == "call_taxi":
            address = params.get("address", "ваш адрес")
            reply = f"🚕 Принято! Вызываю такси на адрес: {address}. Машина будет через 4 минуты."
        elif action == "order_food":
            item = params.get("item", "еду")
            reply = f"🍔 Ищу лучшие предложения по запросу '{item}'. Оформил заказ на ближайшую доставку!"
        else: 
            reply = params.get("reply", "Я вас услышал.")

        return {"answer": reply}

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return {"answer": f"⚠️ Ошибка на сервере: {e}"}

if __name__ == "__main__":
    print("🚀 Сервер УЖЕ с памятью запущен!")
    uvicorn.run(app, host="127.0.0.1", port=8000)