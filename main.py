from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn
import asyncio
from concurrent.futures import ThreadPoolExecutor
from ai_brain import ask_uje_router
from memory import init_db, save_fact, get_all_facts

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

# --- ЭНДПОИНТ ДЛЯ АФИШИ ---
@app.get("/api/promo")
async def get_promo():
    promo_data = {
        "active": True, 
        "image_url": "https://sun9-53.vkuserphoto.ru/s/v1/ig2/Iar_wLzl3QXGfVTTQgJ8s7WG-ealc62pd7qWf2b6BiplZXugbdkZM_z9rpOQ_NO3hpVywKFV8BR7xR77NfAGS3Z8.jpg?quality=95&as=32x32,48x48,72x72,108x108,160x160,240x240,360x360,480x480,540x540,640x640,720x720,1024x1024&from=bu&u=qVNf3at28_Nw0aHMXEsoOEBDtp-oLeT3Gw83_tJSTjo&cs=1024x0", 
        "text": "🔥 Закрытый гастроужин 15 ноября. Осталось 3 места! Жми на кнопку ниже."
    }
    return promo_data

@app.post("/api/ask")
async def ask_bot(message: UserMessage):
    user_text = message.text.strip().lower()
    print(f"📥 Получено: {user_text}") 
    
    KEY_NAMES = {
        "home_address": "🏠 Домашний адрес", "work_address": "🏢 Рабочий адрес",
        "favorite_coffee": "☕ Любимый кофе", "favorite_food": "🍔 Любимая еда",
        "job": "💼 Работа", "hobbies": "🎨 Хобби", "pet": "🐶 Питомец",
        "family": "👨‍👩‍👧 Семья", "car": "🚗 Машина", "name": "👤 Имя",
        "city": "🏙 Город", "age": "🎂 Возраст", "favorite_drink": "🍸 Любимый напиток"
    }
    
    # 1. ПРОВЕРКА: Что бот знает?
    if "что ты обо мне знаешь" in user_text or "моя память" in user_text:
        facts = get_all_facts()
        if not facts:
            return {"answer": "Я пока ничего о тебе не знаю. Нажми кнопку «📝 О себе» или просто напиши мне о себе!"}
        
        reply = "🧠 Вот что я о тебе помню:\n\n"
        for k, v in facts.items():
            ru_key = KEY_NAMES.get(k, k) 
            reply += f"• {ru_key}: {v}\n"
        return {"answer": reply}
    
    # 2. МАНИФЕСТ: ЧЕМ Я ЛУЧШЕ ИИ?
    if "чем я лучше ии" in user_text or "моя мощь" in user_text:
        reply = (
            "🚀 **В чем моя сила? Чем я отличаюсь от ChatGPT и DeepSeek?**\n\n"
            "Многие думают, что я — просто еще один чат с нейросетью. Это не так. Вот 4 главных отличия:\n\n"
            "🧠 **1. Я помню тебя.**\n"
            "Обычный ИИ — как золотая рыбка. Закрыл вкладку — он забыл твое имя. Я же запоминаю твои привычки, адреса и любимый кофе навсегда.\n\n"
            "🎯 **2. Я действую, а не советую.**\n"
            "Спроси у ChatGPT «как вызвать такси» — он напишет инструкцию. Скажи мне «Вызови такси» — и я (в ближайшем будущем) реально вызову машину.\n\n"
            "🎙️ **3. Zero-UI (Голос в ушах).**\n"
            "ChatGPT требует, чтобы ты печатал. Я живу в твоем телефоне. Нажал кнопку, сказал «Уже, как дела?» — и получил ответ голосом.\n\n"
            "🌍 **4. Я знаю контекст.**\n"
            "ChatGPT не знает, где ты. Я же знаю твою геолокацию и время суток. Если на улице -20, я не предложу тебе пойти в парк, а предложу такси.\n\n"
            "**Итог:** ChatGPT — это библиотекарь. А я — твой личный Джарвис. Я знаю всё то же самое, но живу в твоем кармане и выполняю приказы."
        )
        return {"answer": reply}

    # 3. ОБРАБОТКА КЛИКА ПО АФИШЕ (ГАСТРОУЖИН)
    if "хочу на гастроужин" in user_text or "гастроужин" in user_text:
        reply = (
            "🍷 Отличный выбор! Это закрытый ужин на 10 человек.\n\n"
            "📅 Дата: 15 ноября, 19:00\n"
            "💰 Стоимость: 5000 ₽\n\n"
            "Я забронировал за вами место. Для подтверждения и оплаты, пожалуйста, свяжитесь с организатором (@yakovnikandrov) или нажмите кнопку ниже."
        )
        return {"answer": reply}

    # 4. ТРИГГЕР ДЛЯ РАССКАЗА О СЕБЕ
    if "рассказать о себе" in user_text:
        reply = (
            "Отлично! 👤 Расскажи мне о себе всё, что считаешь важным: как тебя зовут, где ты живешь, кем работаешь, что любишь есть и пить, есть ли у тебя питомцы или хобби.\n\n"
            "Можешь написать всё одним сообщением или наговорить голосом. Я всё запомню и буду использовать в будущем!"
        )
        return {"answer": reply}

    # 5. ОТПРАВКА В ИИ (для всего остального)
    try:
        user_facts = get_all_facts()
        loop = asyncio.get_running_loop()
        intent = await loop.run_in_executor(executor, ask_uje_router, message.text, user_facts)
        
        action = intent.get("action")
        params = intent.get("params", {})
        new_facts = intent.get("new_facts", {})
        
        print(f"🧠 ИИ решил: {action} | Параметры: {params} | Новые факты: {new_facts}")

        saved_count = 0
        for key, value in new_facts.items():
            save_fact(key, value)
            saved_count += 1
            print(f"💾 Запомнил: {key} = {value}")

        if action == "help":
            reply = (
                "Я — твой цифровой дворецкий. Вот что я умею:\n\n"
                "🚕 Транспорт: Вызову такси (просто скажи 'Вызови такси домой').\n"
                "🍔 Еда: Найду и закажу еду (скажи 'Хочу мой обычный кофе').\n"
                "🎭 Досуг: Найду афишу.\n\n"
                "💡 *Совет:* Напиши мне один большой текст о себе, и я запомню всё это навсегда!"
            )
        elif action == "call_taxi":
            address = params.get("address", "ваш адрес")
            reply = f"🚕 Принято! Вызываю такси на адрес: {address}. Машина будет через 4 минуты."
        elif action == "order_food":
            item = params.get("item", "еду")
            reply = f"🍔 Ищу лучшие предложения по запросу '{item}'. Оформил заказ на ближайшую доставку!"
        else: 
            reply = params.get("reply", "Я вас услышал.")
            if saved_count > 0:
                reply += f"\n\n🧠 *Я запомнил {saved_count} новых фактов о тебе!*"

        return {"answer": reply}

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return {"answer": f"⚠️ Ошибка на сервере: {e}"}

if __name__ == "__main__":
    print("🚀 Сервер УЖЕ запущен!")
    uvicorn.run(app, host="127.0.0.1", port=8000)