# ai_brain.py
import os
import json
from dotenv import load_dotenv
from langchain_community.chat_models import ChatYandexGPT
from langchain_core.messages import HumanMessage, SystemMessage
from prompts import ROUTER_SYSTEM_PROMPT, BRIEFING_PROMPT

load_dotenv()

llm = ChatYandexGPT(
    api_key=os.getenv("YC_API_KEY"),
    folder_id=os.getenv("YC_FOLDER_ID"),
    model_name="yandexgpt-lite", 
    temperature=0.6 # Чуть выше, чтобы юмор был разнообразнее
)

def ask_uje_router(user_text: str, user_facts: dict) -> dict:
    facts_str = "\n".join([f"- {k}: {v}" for k, v in user_facts.items()])
    if not facts_str: facts_str = "Пока ничего не известно."
    
    system_prompt = ROUTER_SYSTEM_PROMPT.replace("{facts}", facts_str)
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_text)]

    try:
        response = llm.invoke(messages)
        content = response.content.strip()
        start_idx = content.find('{')
        decoder = json.JSONDecoder()
        parsed_obj, _ = decoder.raw_decode(content[start_idx:])
        
        if "action" not in parsed_obj: parsed_obj["action"] = "chat"
        if "params" not in parsed_obj: parsed_obj["params"] = {}
        if "new_facts" not in parsed_obj: parsed_obj["new_facts"] = {}
        return parsed_obj
    except Exception as e:
        print(f"❌ Ошибка JSON: {e}. Ответ: {response.content}")
        return {"action": "chat", "params": {"reply": "Я завис. Повтори."}, "new_facts": {}}

def generate_briefing(weather: str, traffic: str, currency: str, news: str, name: str = "Яков") -> str:
    """Генерирует утренний брифинг с юмором"""
    prompt = BRIEFING_PROMPT.format(
        weather=weather, traffic=traffic, currency=currency, news=news
    )
    try:
        response = llm.invoke([SystemMessage(content=prompt)])
        return response.content.strip().replace("*", "")
    except Exception as e:
        print(f"❌ Ошибка брифинга: {e}")
        return f"Доброе утро, {name}. Погода: {weather}. Пробки: {traffic}. Новости: {news}."