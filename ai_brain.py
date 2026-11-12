# ai_brain.py
import os
import json
from dotenv import load_dotenv
from langchain_community.chat_models import ChatYandexGPT
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from prompts import ROUTER_SYSTEM_PROMPT, BRIEFING_PROMPT, FILE_ANALYSIS_PROMPT

load_dotenv()

llm = ChatYandexGPT(
    api_key=os.getenv("YC_API_KEY"),
    folder_id=os.getenv("YC_FOLDER_ID"),
    model_name="yandexgpt-lite", 
    temperature=0.3
)

def ask_gpt_free(user_text: str, history: list = None) -> str:
    messages = [SystemMessage(content="Ты — БашГид, живой, дружелюбный местный гид по Башкирии. Общайся на 'ты', тепло, с юмором и без канцеляризмов. Помогай туристам, отвечай кратко и по делу.")]
    if history:
        for msg in history[-6:]:
            if msg["role"] == "user": messages.append(HumanMessage(content=msg["text"]))
            elif msg["role"] == "bot": messages.append(AIMessage(content=msg["text"]))
    messages.append(HumanMessage(content=user_text))
    try:
        response = llm.invoke(messages)
        return response.content.strip().replace("**", "")
    except Exception:
        return "Слушай, у меня тут небольшие помехи со связью. Давай еще раз попробуем?"

def ask_uje_router(user_text: str, user_facts: dict, history: list = None) -> dict:
    facts_str = "\n".join([f"- {k}: {v}" for k, v in user_facts.items()])
    if not facts_str: facts_str = "Пока ничего не известно."
    
    system_prompt = ROUTER_SYSTEM_PROMPT.replace("{facts}", facts_str)
    # ✅ ДОБАВЛЕНО ЖЕСТКОЕ ПРАВИЛО, ЧТОБЫ НЕ ЗАЦИКЛИВАЛО
    system_prompt += "\nВНИМАНИЕ: Если в фактах УЖЕ есть имя и город пользователя, НИКОГДА не присылай их снова в new_facts. Просто общайся."
    
    messages = [SystemMessage(content=system_prompt)]
    if history:
        for msg in history[-10:]:
            if msg["role"] == "user": messages.append(HumanMessage(content=msg["text"]))
            elif msg["role"] == "bot": messages.append(AIMessage(content=msg["text"]))
    messages.append(HumanMessage(content=user_text))

    try:
        response = llm.invoke(messages)
        content = response.content.strip()
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
        return {"action": "chat", "params": {"reply": ask_gpt_free(user_text, history)}, "new_facts": {}}

def generate_briefing(weather: str, traffic: str, currency: str, news: str, name: str = "друг") -> str:
    prompt = BRIEFING_PROMPT.format(weather=weather, traffic=traffic, currency=currency, news=news)
    try:
        response = llm.invoke([SystemMessage(content=prompt)])
        return response.content.strip().replace("**", "")
    except Exception:
        return f"Доброе утро, {name}. Погода: {weather}."

def analyze_file_text(file_text: str, user_role: str, filename: str) -> str:
    prompt = FILE_ANALYSIS_PROMPT.format(role=user_role, filename=filename, text=file_text[:4000])
    try:
        response = llm.invoke([SystemMessage(content=prompt)])
        return response.content.strip().replace("**", "")
    except Exception:
        return "Я прочитал файл, но не смог его проанализировать."