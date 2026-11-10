from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn
import asyncio
from concurrent.futures import ThreadPoolExecutor
from ai_brain import ask_uje_router
from memory import init_db, save_fact, get_all_facts
from tools import get_weather

app = FastAPI()
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

@app.get("/api/promo")
async def get_promo():
    return {
        "active": True, 
        "image_url": "https://sun9-53.vkuserphoto.ru/s/v1/ig2/Iar_wLzl3QXGfVTTQgJ8s7WG-ealc62pd7qWf2b6BiplZXugbdkZM_z9rpOQ_NO3hpVywKFV8BR7xR77NfAGS3Z8.jpg?quality=95&as=32x32,48x48,72x72,108x108,160x160,240x240,360x360,480x480,540x540,640x640,720x720,1024x1024&from=bu&u=qVNf3at28_Nw0aHMXEsoOEBDtp-oLeT3Gw83_tJSTjo&cs=1024x0", 
        "text": "🔥 Закрытый гастроужин 15 ноября. Осталось 3 места! Жми на кнопку ниже."
    }

@app.post("/api/ask")
async def ask_bot(message: UserMessage):
    user_text = message.text.strip()
    print(f"📥 Получено: {user_text}") 
    
    KEY_NAMES = {
        "home_address": "🏠 Домашний адрес", "work_address": "🏢 Рабочий адрес",
        "favorite_coffee": "☕ Любимый кофе", "pet": "🐶 Питомец",
        "job": "💼 Работа", "name": "👤 Имя", "city": "🏙 Город"
    }
    
    # 1. ОБУЧАЮЩИЕ КНОПКИ
    if "лень 2.0" in user_text.lower() or "наушники" in user_text.lower():
        reply = (
            "🎧 **Наша суперсила — Лень 2.0.**\n\n"
            "Представь: ты стоишь на кухне, руки в муке, а телефон лежит в другой комнате. Ты просто говоришь в наушники: «Уже, как приготовить винегрет?» — и я отвечаю голосом прямо в уши. Или: «Вызови такси». \n\n"
            "Никаких экранов, кнопок и отвлечений. Просто голос. В будущем мы сделаем так, чтобы я работал в фоне 24/7, как Алиса, но только для твоих бытовых задач. Не доставая телефон из кармана. Вот это и есть Лень 2.0."
        )
        return {"answer": reply}

    if "чем я лучше ии" in user_text.lower() or "моя мощь" in user_text.lower():
        reply = (
            "🚀 **Чем я отличаюсь от ChatGPT и DeepSeek?**\n\n"
            "🧠 **1. Я помню тебя.** Обычный ИИ забывает тебя, как только ты закрыл вкладку. Я же запоминаю твои привычки, адреса и любимый кофе навсегда.\n\n"
            "🎯 **2. Я действую, а не советую.** ChatGPT напишет инструкцию «как вызвать такси». А я реально вызову машину.\n\n"
            "🎙️ **3. Zero-UI (Голос в ушах).** ChatGPT требует, чтобы ты печатал. Я живу в твоем телефоне и наушниках. Нажал кнопку, сказал «Уже, как дела?» — и получил ответ голосом.\n\n"
            "**Итог:** ChatGPT — это библиотекарь. А я — твой личный Джарвис."
        )
        return {"answer": reply}

    if "тест памяти" in user_text.lower():
        reply = (
            "🧠 **Давай проверим мою память.**\n\n"
            "Напиши мне ОДНО сообщение (или наговори голосом) о себе. Например: *«Меня зовут Яков, я живу в Уфе, работаю предпринимателем, люблю капучино и собак»*.\n\n"
            "А потом нажми кнопку «Посмотреть память». Я всё это запомню и покажу!"
        )
        return {"answer": reply}

    if "приготовь винегрет" in user_text.lower():
        reply = (
            "🍳 **Рецепт винегрета (слушай в наушниках, не отвлекаясь от готовки):**\n\n"
            "1. Отвари свеклу, морковь и картофель до готовности. Остуди и нарежь кубиками.\n"
            "2. Нарежь соленые огурцы и квашеную капусту.\n"
            "3. Добавь зеленый горошек.\n"
            "4. Заправь подсолнечным маслом.\n"
            "5. Посоли по вкусу. Приятного аппетита!"
        )
        return {"answer": reply}

    # 2. ПРОСМОТР ПАМЯТИ
    if "посмотреть память" in user_text.lower() or "что ты обо мне знаешь" in user_text.lower():
        facts = get_all_facts()
        if not facts:
            return {"answer": "Память пока пустая. Нажми «Тест памяти» и расскажи о себе!"}
        
        reply = "🧠 Вот что я о тебе помню:\n\n"
        for k, v in facts.items():
            ru_key = KEY_NAMES.get(k, k) 
            reply += f"• {ru_key}: {v}\n"
        return {"answer": reply}

    # 3. ОТПРАВКА В ИИ
    try:
        user_facts = get_all_facts()
        loop = asyncio.get_running_loop()
        intent = await loop.run_in_executor(executor, ask_uje_router, user_text, user_facts)
        
        action = intent.get("action", "chat")
        params = intent.get("params", {})
        new_facts = intent.get("new_facts", {})
        
        print(f"🧠 ИИ решил: {action} | Параметры: {params} | Новые факты: {new_facts}")

        saved_count = 0
        for key, value in new_facts.items():
            save_fact(key, value)
            saved_count += 1
            print(f"💾 Запомнил: {key} = {value}")

        # ВЫПОЛНЕНИЕ ДЕЙСТВИЙ
        if action == "get_weather":
            city = params.get("city", user_facts.get("city", "Уфа"))
            # Запускаем запрос погоды в отдельном потоке, чтобы не вешать сервер
            weather_text = await loop.run_in_executor(executor, get_weather, city)
            reply = f"🌤 {weather_text}"
            
        elif action == "route_home":
            address = params.get("address") or user_facts.get("home_address")
            if address:
                reply = f"🚕 Домой. Адрес помню: {address}. Вызываю машину."
            else:
                reply = "🚕 Готов вызвать такси. Но я пока не знаю твой домашний адрес. Скажи его, и я запомню."
                
        elif action == "my_coffee":
            coffee = params.get("item") or user_facts.get("favorite_coffee")
            if coffee:
                reply = f"☕ Ваш обычный {coffee}. Заказываю."
            else:
                reply = "☕ Какой кофе вы предпочитаете? Я запомню на будущее."
                
        else:
            reply = params.get("reply", "Я вас услышал.")
            if saved_count > 0:
                reply += f"\n\n🧠 *Я запомнил {saved_count} новых факт(ов) о тебе!*"

        return {"answer": reply}

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return {"answer": f"⚠️ Ошибка на сервере: {e}"}

if __name__ == "__main__":
    print("🚀 Сервер УЖЕ запущен!")
    uvicorn.run(app, host="127.0.0.1", port=8000)