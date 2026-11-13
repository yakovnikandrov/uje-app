# ai_brain.py
import os
import json
import requests
from dotenv import load_dotenv
from prompts import ROUTER_SYSTEM_PROMPT, BRIEFING_PROMPT, FILE_ANALYSIS_PROMPT

load_dotenv()

YC_API_KEY = os.getenv("YC_API_KEY")
YC_FOLDER_ID = os.getenv("YC_FOLDER_ID")
API_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

def _call_yandex_gpt(messages: list, temperature: float = 0.3) -> str:
    """Прямой запрос к YandexGPT API."""
    if not YC_API_KEY or not YC_FOLDER_ID:
        print("❌ Нет ключей YandexGPT")
        return ""

    headers = {
        "Authorization": f"Api-Key {YC_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "modelUri": f"gpt://{YC_FOLDER_ID}/yandexgpt-lite",
        "completionOptions": {
            "stream": False,
            "temperature": temperature,
            "maxTokens": "2000"
        },
        "messages": messages
    }

    try:
        response = requests.post(API_URL, headers=headers, json=data, timeout=15)
        response.raise_for_status()
        result = response.json()
        return result['result']['alternatives'][0]['message']['text'].strip()
    except Exception as e:
        print(f"❌ Ошибка API YandexGPT: {e}")
        return ""

def ask_gpt_free(user_text: str, history: list = None) -> str:
    messages = [{"role": "system", "text": "Ты — БашГид, живой, дружелюбный местный гид по Башкирии. Общайся на 'ты', тепло, с юмором и без канцеляризмов. Помогай туристам, отвечай кратко и по делу."}]
    if history:
        for msg in history[-6:]:
            role = "user" if msg["role"] == "user" else "assistant"
            messages.append({"role": role, "text": msg["text"]})
    messages.append({"role": "user", "text": user_text})
    
    reply = _call_yandex_gpt(messages)
    if not reply:
        return "Слушай, у меня тут небольшие помехи со связью. Давай еще раз попробуем?"
    return reply.replace("**", "")

def ask_uje_router(user_text: str, user_facts: dict, history: list = None) -> dict:
    facts_str = "\n".join([f"- {k}: {v}" for k, v in user_facts.items()])
    if not facts_str: facts_str = "Пока ничего не известно."
    
    system_prompt = ROUTER_SYSTEM_PROMPT.replace("{facts}", facts_str)
    system_prompt += "\nВНИМАНИЕ: Если в фактах УЖЕ есть имя и город пользователя, НИКОГДА не присылай их снова в new_facts. Просто общайся."
    
    messages = [{"role": "system", "text": system_prompt}]
    if history:
        for msg in history[-10:]:
            role = "user" if msg["role"] == "user" else "assistant"
            messages.append({"role": role, "text": msg["text"]})
    messages.append({"role": "user", "text": user_text})

    content = _call_yandex_gpt(messages, temperature=0.1) # Для JSON температура ниже
    
    if not content:
        return {"action": "chat", "params": {"reply": ask_gpt_free(user_text, history)}, "new_facts": {}}

    try:
        start_idx = content.find('{')
        if start_idx == -1:
            return {"action": "chat", "params": {"reply": ask_gpt_free(user_text, history)}, "new_facts": {}}
            
        decoder = json.JSONDecoder()
        parsed_obj, _ = decoder.raw_decode(content[start_idx:])
        
        if "action" not in parsed_obj: parsed_obj["action"] = "chat"
        if "params" not in parsed_obj: parsed_obj["params"] = {}
        if "new_facts" not in parsed_obj: parsed_obj["new_facts"] = {}
        
        if parsed_obj["action"] == "chat" and not parsed_obj["params"].get("reply"):
            parsed_obj["params"]["reply"] = ask_gpt_free(user_text, history)
            
        return parsed_obj
    except Exception as e:
        print(f"❌ Ошибка парсинга JSON: {e}\nОтвет: {content}")
        return {"action": "chat", "params": {"reply": ask_gpt_free(user_text, history)}, "new_facts": {}}

def generate_briefing(weather: str, traffic: str, currency: str, news: str, name: str = "друг") -> str:
    prompt = BRIEFING_PROMPT.format(weather=weather, traffic=traffic, currency=currency, news=news)
    messages = [{"role": "system", "text": prompt}]
    
    reply = _call_yandex_gpt(messages)
    if not reply:
        return f"Доброе утро, {name}. Погода: {weather}."
    return reply.replace("**", "")

def analyze_file_text(file_text: str, user_role: str, filename: str) -> str:
    prompt = FILE_ANALYSIS_PROMPT.format(filename=filename, text=file_text[:4000])
    messages = [{"role": "system", "text": prompt}]
    
    reply = _call_yandex_gpt(messages)
    if not reply:
        return "Я прочитал файл, но не смог его проанализировать."
    return reply.replace("**", "")