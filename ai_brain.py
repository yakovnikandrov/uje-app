import os
import json
from dotenv import load_dotenv
from langchain_community.chat_models import ChatYandexGPT
from langchain_core.messages import HumanMessage, SystemMessage

load_dotenv()

llm = ChatYandexGPT(
    api_key=os.getenv("YC_API_KEY"),
    folder_id=os.getenv("YC_FOLDER_ID"),
    model_name="yandexgpt-lite", 
    temperature=0.1
)

def ask_uje_router(user_text: str, user_facts: dict) -> dict:
    if "что ты умеешь" in user_text.lower() or "помощь" in user_text.lower():
        return {"action": "help", "params": {}, "new_facts": {}}

    facts_str = "\n".join([f"- {k}: {v}" for k, v in user_facts.items()])
    if not facts_str:
        facts_str = "Пока ничего не известно."

    system_prompt = f"""
    Ты — маршрутизатор цифрового дворецкого 'УЖЕ'. Твоя задача — понять намерение пользователя и извлечь факты о нем.
    
    ВОТ ЧТО ТЫ УЖЕ ЗНАЕШЬ О ПОЛЬЗОВАТЕЛЕ:
    {facts_str}
    
    Верни ТОЛЬКО валидный JSON (без markdown).
    Формат: {{"action": "действие", "params": {{...}}, "new_facts": {{...}}}}
    
    Доступные действия (action):
    - "call_taxi": Пользователь просит такси. Параметры: {{"address": "адрес"}}.
    - "order_food": Просит еду. Параметры: {{"item": "что именно"}}.
    - "chat": Обычный разговор. Параметры: {{"reply": "короткий ответ"}}.
    
    ИЗВЛЕЧЕНИЕ ФАКТОВ (new_facts):
    Если пользователь присылает много информации о себе (эссе, резюме, список привычек), извлеки ВСЕ факты.
    Ключи для памяти могут быть любыми (например: "home_address", "favorite_coffee", "job", "hobbies", "car", "family", "favorite_food"). Значение — строка.
    
    Пример ответа на текст "Я живу на Ленина 10, работаю в IT, люблю капучино и собаку по кличке Бублик":
    {{"action": "chat", "params": {{"reply": "Принято! Записал всё в память."}}, "new_facts": {{"home_address": "ул. Ленина 10", "job": "IT-специалист", "favorite_coffee": "капучино", "pet": "собака Бублик"}}}}
    """

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_text)
    ]

    try:
        response = llm.invoke(messages)
        clean_json = response.content.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)
    except Exception as e:
        print(f"Ошибка парсинга JSON: {e}")
        return {"action": "chat", "params": {"reply": "Я немного завис. Повтори, пожалуйста."}, "new_facts": {}}