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
    if not YC_API_KEY or not YC_FOLDER_ID: return ""
    headers = {"Authorization": f"Api-Key {YC_API_KEY}", "Content-Type": "application/json"}
    data = {"modelUri": f"gpt://{YC_FOLDER_ID}/yandexgpt-lite", "completionOptions": {"stream": False, "temperature": temperature, "maxTokens": "2000"}, "messages": messages}
    try:
        res = requests.post(API_URL, headers=headers, json=data, timeout=15)
        res.raise_for_status()
        return res.json()['result']['alternatives'][0]['message']['text'].strip()
    except Exception as e:
        print(f"❌ Ошибка API YandexGPT: {e}")
        return ""

def ask_gpt_free(user_text: str, history: list = None) -> str:
    messages = [{"role": "system", "text": "Ты — БашГид, живой, дружелюбный гид (женщина) по Башкирии. Общайся на 'ты', тепло, с юмором. Помогай туристам."}]
    if history:
        for msg in history[-6:]: messages.append({"role": "user" if msg["role"] == "user" else "assistant", "text": msg["text"]})
    messages.append({"role": "user", "text": user_text})
    return _call_yandex_gpt(messages).replace("**", "") or "Слушай, у меня тут небольшие помехи со связью. Давай еще раз попробуем?"

def ask_uje_router(user_text: str, user_facts: dict, history: list = None) -> dict:
    facts_str = "\n".join([f"- {k}: {v}" for k, v in user_facts.items()]) or "Пока ничего не известно."
    system_prompt = ROUTER_SYSTEM_PROMPT.replace("{facts}", facts_str)
    messages = [{"role": "system", "text": system_prompt}]
    if history:
        for msg in history[-10:]: messages.append({"role": "user" if msg["role"] == "user" else "assistant", "text": msg["text"]})
    messages.append({"role": "user", "text": user_text})

    content = _call_yandex_gpt(messages, temperature=0.1)
    if not content: return {"action": "chat", "params": {"reply": ask_gpt_free(user_text, history)}, "new_facts": {}}
    try:
        start_idx = content.find('{')
        if start_idx == -1: return {"action": "chat", "params": {"reply": ask_gpt_free(user_text, history)}, "new_facts": {}}
        parsed_obj, _ = json.JSONDecoder().raw_decode(content[start_idx:])
        if "action" not in parsed_obj: parsed_obj["action"] = "chat"
        if "params" not in parsed_obj: parsed_obj["params"] = {}
        if "new_facts" not in parsed_obj: parsed_obj["new_facts"] = {}
        if parsed_obj["action"] == "chat" and not parsed_obj["params"].get("reply"): parsed_obj["params"]["reply"] = ask_gpt_free(user_text, history)
        return parsed_obj
    except:
        return {"action": "chat", "params": {"reply": ask_gpt_free(user_text, history)}, "new_facts": {}}

def generate_briefing(weather: str, traffic: str, currency: str, news: str, name: str = "друг") -> str:
    prompt = BRIEFING_PROMPT.format(weather=weather, traffic=traffic, currency=currency, news=news)
    return _call_yandex_gpt([{"role": "system", "text": prompt}]).replace("**", "") or f"Доброе утро, {name}. Погода: {weather}."

def analyze_file_text(file_text: str, user_role: str, filename: str) -> str:
    prompt = FILE_ANALYSIS_PROMPT.format(filename=filename, text=file_text[:4000])
    return _call_yandex_gpt([{"role": "system", "text": prompt}]).replace("**", "") or "Я прочитала файл, но не смогла его проанализировать."