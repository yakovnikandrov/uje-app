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
    Верни ТОЛЬКО валидный JSON (без markdown).
    
    ВОТ ЧТО ТЫ ЗНАЕШЬ О ПОЛЬЗОВАТЕЛЕ:
    {facts_str}
    
    Формат: {{"action": "имя", "params": {{...}}, "new_facts": {{...}}}}
    
    ДЕЙСТВИЯ (action):
    - "get_weather": погода. Параметры: {{"city": "город"}}.
    - "call_taxi": такси. Параметры: {{"destination": "куда"}}. Если не знаешь куда, спроси.
    - "check_bus": автобус. Параметры: {{}}.
    - "play_music": музыка. Параметры: {{"genre": "жанр"}}.
    - "order_food": еда. Параметры: {{"dish": "что именно"}}.
    - "save_fact": сохранить факт (имя, город, адрес дома, любимый кофе, любимая еда). Извлекай в "new_facts".
    - "chat": обычный ответ. Параметры: {{"reply": "ответ"}}.
    
    ВАЖНО: Если пользователь говорит "Вызови такси домой", проверь, есть ли "home_address" в фактах. Если есть — используй его. Если нет — action="chat", reply="Куда вызываем такси? Я пока не знаю ваш адрес дома."
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