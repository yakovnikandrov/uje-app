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
    temperature=0.0
)

def ask_uje_router(user_text: str, user_facts: dict) -> dict:
    facts_str = "\n".join([f"- {k}: {v}" for k, v in user_facts.items()])
    if not facts_str:
        facts_str = "Пока ничего не известно."

    system_prompt = f"""
    Ты — строгий маршрутизатор ИИ-дворецкого 'УЖЕ'. 
    Твоя задача — определить намерение пользователя и вернуть ТОЛЬКО валидный JSON (без markdown).
    
    ВОТ ЧТО ТЫ ЗНАЕШЬ О ПОЛЬЗОВАТЕЛЕ:
    {facts_str}
    
    Формат ответа: {{"action": "имя_действия", "params": {{...}}, "new_facts": {{...}}}}
    
    СПИСОК ДОСТУПНЫХ ДЕЙСТВИЙ (action):
    - "get_weather": пользователь спрашивает о погоде. Параметры: {{"city": "название города"}}.
    - "route_home": пользователь хочет домой. Если в памяти есть "home_address", возьми оттуда.
    - "my_coffee": хочет свой обычный кофе. Если в памяти есть "favorite_coffee", возьми оттуда, иначе спроси.
    - "get_memory": хочет узнать, что ты о нем знаешь.
    - "manifesto": хочет узнать, чем ты лучше ChatGPT.
    - "save_fact": пользователь сообщает новый факт о себе. Извлеки его в "new_facts" (ключи: name, city, job, favorite_coffee, pet, home_address, work_address).
    - "chat": любая другая фраза, не подходящая под действия. В params передай {{"reply": "короткий ответ в стиле дворецкого"}}.
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
        print(f"Ошибка парсинга JSON: {e}. Ответ ИИ: {response.content[:100]}")
        return {"action": "chat", "params": {"reply": "Я немного завис. Повтори, пожалуйста."}, "new_facts": {}}