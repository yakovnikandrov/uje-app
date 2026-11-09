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
    """
    Анализирует запрос, учитывая память о пользователе, и возвращает действие.
    """
    if "что ты умеешь" in user_text.lower() or "помощь" in user_text.lower():
        return {"action": "help", "params": {}, "new_facts": {}}

    # Формируем строку с фактами о пользователе для ИИ
    facts_str = "\n".join([f"- {k}: {v}" for k, v in user_facts.items()])
    if not facts_str:
        facts_str = "Пока ничего не известно."

    system_prompt = f"""
    Ты — маршрутизатор цифрового дворецкого 'УЖЕ'. Твоя задача — понять намерение пользователя и использовать факты о нем.
    
    ВОТ ЧТО ТЫ УЖЕ ЗНАЕШЬ О ПОЛЬЗОВАТЕЛЕ:
    {facts_str}
    
    Твоя задача — вернуть ТОЛЬКО валидный JSON (без markdown).
    Формат: {{"action": "действие", "params": {{...}}, "new_facts": {{...}}}}
    
    Доступные действия (action):
    - "call_taxi": Пользователь просит такси. Параметры: {{"address": "адрес"}}. 
      ВАЖНО: Если пользователь говорит "домой", подставь домашний адрес из фактов.
    - "order_food": Просит еду/кофе. Параметры: {{"item": "что именно"}}.
      ВАЖНО: Если просит "мой обычный кофе", подставь любимый напиток из фактов.
    - "chat": Обычный разговор. Параметры: {{"reply": "короткий ответ дворецкого"}}.
    
    Сохранение новых фактов (new_facts):
    Если пользователь прямо говорит новый адрес или привычку (например: "Запомни, я люблю латте"), добавь это в new_facts.
    Ключи для памяти: "home_address", "work_address", "favorite_coffee", "favorite_food".
    
    Пример ответа: 
    {{"action": "call_taxi", "params": {{"address": "ул. Ленина 10"}}, "new_facts": {{}}}}
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