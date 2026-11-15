# routers/chat.py
from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import List, Dict, Optional
import asyncio, re
from memory import save_fact, get_all_facts, save_pending, get_pending, clear_pending, clear_all_facts
from tools import *
from responses import RESPONSES, NAME_BLACKLIST, CITY_CORES, CITY_REACTIONS
from ai_brain import ask_uje_router, ask_gpt_free

router = APIRouter()

class UserMessage(BaseModel):
    text: str
    history: Optional[List[Dict[str, str]]] = []

@router.post("/api/ask")
async def ask_bot(message: UserMessage):
    user_text = message.text.strip()
    text_lower = user_text.lower()
    facts = get_all_facts()
    transport = facts.get("transport", "неизвестно")

    pending = get_pending()
    
    if user_text == "[call_taxi_start]":
        save_pending("wait_taxi_address", "")
        return {"answer": "Куда поедем? Назови адрес, отель или место, и я вызову такси.", "action": "none"}

    if pending and pending.get("action") == "wait_taxi_address":
        clear_pending()
        end_lat, end_lon = geocode_address(user_text + ", Уфа")
        if end_lat:
            loc_str = facts.get("current_location", "")
            if not loc_str:
                save_pending("wait_geo", f"{end_lat},{end_lon}:{user_text}")
                return {"answer": f"Отлично, едем до {user_text}. Нажми на компас 🧭, чтобы я знала, откуда тебя забрать.", "action": "none"}
            
            start_lat, start_lon = map(float, loc_str.split(','))
            if transport == "машина":
                url = get_auto_map_link(start_lat, start_lon, end_lat, end_lon)
                return {"answer": f"Автомаршрут до {user_text} построен.", "action": "show_card", "card": {"type": "map", "title": "🚗 На авто", "text": user_text, "button": "Открыть Карты", "url": url}}
            else:
                url = get_taxi_link(start_lat, start_lon, end_lat, end_lon)
                return {"answer": f"Маршрут до {user_text} построен.", "action": "show_card", "card": {"type": "taxi", "title": "🚕 Яндекс.Го", "text": user_text, "button": "Открыть Яндекс Go", "url": url}}
        else:
            return {"answer": "Не могу найти такой адрес. Попробуй назвать точнее (например, 'Отель Азимут').", "action": "none"}

    if user_text == "[select_guide:female]":
        clear_all_facts()
        save_fact("guide_gender", "female")
        return {"answer": "Отличный выбор! Я рада приветствовать вас в нашей республике! Как к вам обращаться?", "action": "none", "quick_actions": []}
    
    if user_text == "[select_guide:male]":
        clear_all_facts()
        save_fact("guide_gender", "male")
        return {"answer": "Отличный выбор! Я рад приветствовать вас в нашей республике! Как к вам обращаться?", "action": "none", "quick_actions": []}

    if user_text == "[showcase_list]":
        cards = [
            {"title": "🐎 Салават Юлаев", "desc": "Самая крупная конная статуя в Европе, визитная карточка Уфы.", "image": "/static/img/showcase_salavat_flowers.jpg", "buttons": [{"label": "📍 Как доехать", "action": "[route:walk:Памятник Салавату Юлаеву]"}, {"label": "📖 Подробнее", "action": "[showcase:salavat_flowers]"}]},
            {"title": "🏰 Белый Замок", "desc": "Один из самых фотографируемых объектов города.", "image": "/static/img/showcase_castle.jpg", "buttons": [{"label": "📍 Как доехать", "action": "[route:walk:Белый Замок]"}, {"label": "📖 Подробнее", "action": "[showcase:castle]"}]},
            {"title": "🏛 Монумент Дружбы", "desc": "Гранитный обелиск высотой 35 метров в честь дружбы народов.", "image": "/static/img/showcase_friendship.jpg", "buttons": [{"label": "📍 Как доехать", "action": "[route:walk:Монумент Дружбы]"}, {"label": "📖 Подробнее", "action": "[showcase:friendship]"}]},
            {"title": "🐎 Салават крупным планом", "desc": "Национальный герой Башкирии.", "image": "/static/img/showcase_salavat_close.jpg", "buttons": [{"label": "📍 Как доехать", "action": "[route:walk:Памятник Салавату Юлаеву]"}, {"label": "📖 Подробнее", "action": "[showcase:salavat_close]"}]}
        ]
        return {"answer": "Выбери, что тебе интересно:", "action": "show_cards", "cards": cards}

    if user_text.startswith("[set_home:"):
        place_name = user_text.replace("[set_home:", "").replace("]", "")
        save_fact("home_address", place_name)
        return {"answer": f"Отлично! Запомнила, что ты остановился в {place_name}.", "action": "none"}

    if user_text.startswith("[showcase:"):
        key = user_text.replace("[showcase:", "").replace("]", "")
        name = ""
        if "salavat_flowers" in key or "salavat_close" in key:
            name = "Памятник Салавату Юлаеву"
            ans = "Памятник Салавату Юлаеву — самая крупная конная статуя в Европе. Это визитная карточка Уфы."
        elif "friendship" in key:
            name = "Монумент Дружбы"
            ans = "Монумент Дружбы — это гранитный обелиск высотой 35 метров."
        elif "castle" in key:
            name = "Белый Замок"
            ans = "Этот белоснежный замок — один из самых фотографируемых объектов Уфы."
        
        return {"answer": ans, "action": "none", "image": f"/static/img/showcase_{key}.jpg", "buttons": [
            {"label": "📍 Как доехать", "action": f"[route:walk:{name}]"},
            {"label": "📖 Другие места", "action": "[showcase_list]"}
        ]}

    if user_text.startswith("[map:"):
        place_name = user_text.replace("[map:", "").replace("]", "")
        return {"answer": f"Ты выбрал: {place_name}. Вот что я знаю об этом месте.", "action": "none", "buttons": [
            {"label": "📍 Как доехать", "action": f"[route:walk:{place_name}]"},
            {"label": "📖 Подробнее", "action": f"[details_attr:history:{place_name}]"}
        ]}

    if user_text.lower() == "хочу сюда":
        return {"answer": "Отлично! Выбери место из списка, и я проложу маршрут.", "action": "none"}

    if any(word in text_lower for word in ["хочу в", "поехали в", "веди в", "поедем в", "хочу на"]):
        for attr_key, items in ATTRACTIONS.items():
            for item in items:
                if item["name"].lower() in text_lower:
                    return {"answer": f"Отличный выбор! Как поедем до {item['name']}?", "action": "none", "buttons": [
                        {"label": "🚕 Такси", "action": f"[route:taxi:{item['coords'][0]},{item['coords'][1]}:{item['name']}]"},
                        {"label": "🚗 На авто", "action": f"[route:auto:{item['coords'][0]},{item['coords'][1]}:{item['name']}]"},
                        {"label": "🚌 Автобус", "action": f"[route:bus:{item['coords'][0]},{item['coords'][1]}:{item['name']}]"},
                        {"label": "🚶 Пешком", "action": f"[route:walk:{item['coords'][0]},{item['coords'][1]}:{item['name']}]"}
                    ]}

    if user_text.lower() in ["доехал", "доехала", "приехал", "приехала", "на месте", "пришел", "пришла", "здесь", "тут"]:
        clear_pending()
        return {"answer": "Отлично! Рад, что ты добрался. Теперь давай решим, чем займемся: поедим, погуляем или построим маршрут по интересам?", "action": "none", "buttons": [
            {"label": "🍽 Где поесть", "action": "[food_start]"},
            {"label": "🏛 Что посмотреть", "action": "[attr_history]"},
            {"label": "📅 Маршрут по интересам", "action": "[route_interests_start]"}
        ]}

    if user_text.lower() in ["дальше", "далее", "next", "иду", "готово", "сделал"]:
        pending = get_pending()
        if pending and pending.get("action") == "guide_route":
            parts = pending.get("params").split("|")
            name = parts[0]
            mode = parts[1]
            step_idx = int(parts[2]) + 1
            
            route_data = DEMO_ROUTES.get(name)
            if route_data and mode in route_data:
                steps = route_data[mode]
                if step_idx < len(steps):
                    save_pending("guide_route", f"{name}|{mode}|{step_idx}")
                    return {"answer": f"Шаг {step_idx + 1}: {steps[step_idx]}\n\nНапиши 'Дальше', когда выполнишь.", "action": "none"}
                else:
                    clear_pending()
                    return {"answer": f"🎉 Поздравляю! Ты на месте — {name}. Приятного отдыха! Если что, я рядом.", "action": "none"}
        else:
            return {"answer": "Я не вижу активного маршрута. Сначала выбери, куда мы идем (например, через меню «Маршрут по интересам»).", "action": "none"}

    if user_text == "[route_interests_start]":
        return {"answer": "Отлично! Давай соберём твой идеальный день. Что тебе интереснее?", "action": "none", "buttons": [
            {"label": "🏛 История и музеи", "action": "[ri_interest:history]"},
            {"label": "🌳 Природа и прогулки", "action": "[ri_interest:nature]"},
            {"label": "🍽 Гастрономия", "action": "[ri_interest:food]"},
            {"label": "🚶 Всё сразу (микс)", "action": "[ri_interest:mix]"}
        ]}

    if user_text.startswith("[ri_interest:"):
        interest = user_text.replace("[ri_interest:", "").replace("]", "")
        save_fact("current_route_interest", interest)
        
        weather_data = get_real_weather("Уфа")
        is_bad_weather = False
        try:
            temp_str = weather_data.split('°')[0]
            temp = int(re.sub(r'[^\d-]', '', temp_str))
            if temp < 5 or "дождь" in weather_data.lower() or "снег" in weather_data.lower():
                is_bad_weather = True
        except: pass

        if is_bad_weather and interest in ["nature", "mix"]:
            return {"answer": f"Слушай, на улице сейчас {weather_data}. Для прогулок не очень. Давай я заменю природу на уютные места, чтобы не мёрзнуть?", "action": "none", "buttons": [
                {"label": "✅ Да, давай в тепло", "action": "[ri_agree_weather]"},
                {"label": "❄️ Нет, хочу гулять", "action": "[ri_force_weather]"}
            ]}

        route = DEMO_INTEREST_ROUTES.get(interest)
        if route:
            text = f"Вот твой маршрут: {route['title']}\n\n"
            for step in route["steps"]:
                text += f"{step['text']}\n\n"
            
            buttons = []
            for step in route["steps"]:
                name_part = step.get('place', step['text'].split('—')[1].split('(')[0].strip())
                buttons.append({"label": f"📖 {name_part}", "action": step['action']})
            
            first_place_name = route['steps'][0].get('place', route['steps'][0]['text'].split('—')[1].split('(')[0].strip())
            buttons.append({"label": "📍 Всё круто, веди меня", "action": f"[route:walk:{first_place_name}]"})
            
            return {"answer": text, "action": "none", "buttons": buttons}

    if user_text == "[ri_agree_weather]":
        save_fact("current_route_interest", "bad_weather_offer")
        route = DEMO_INTEREST_ROUTES["bad_weather_offer"]
        text = f"Отлично! Вот твой маршрут: {route['title']}\n\n" + "\n\n".join([s['text'] for s in route["steps"]])
        buttons = []
        for step in route["steps"]:
            name_part = step.get('place', step['text'].split('—')[1].split('(')[0].strip())
            buttons.append({"label": f"📖 {name_part}", "action": step['action']})
        first_place_name = route['steps'][0].get('place', route['steps'][0]['text'].split('—')[1].split('(')[0].strip())
        buttons.append({"label": "📍 Всё круто, веди меня", "action": f"[route:walk:{first_place_name}]"})
        return {"answer": text, "action": "none", "buttons": buttons}

    if user_text == "[ri_force_weather]":
        save_fact("current_route_interest", "nature")
        route = DEMO_INTEREST_ROUTES["nature"]
        text = f"Ну смотри, ты сам выбрал! Одевайся потеплее.\n\nВот твой маршрут: {route['title']}\n\n" + "\n\n".join([s['text'] for s in route["steps"]])
        buttons = []
        for step in route["steps"]:
            name_part = step.get('place', step['text'].split('—')[1].split('(')[0].strip())
            buttons.append({"label": f"📖 {name_part}", "action": step['action']})
        first_place_name = route['steps'][0].get('place', route['steps'][0]['text'].split('—')[1].split('(')[0].strip())
        buttons.append({"label": "📍 Всё круто, веди меня", "action": f"[route:walk:{first_place_name}]"})
        return {"answer": text, "action": "none", "buttons": buttons}

    if user_text.startswith("[ri_details:"):
        parts = user_text.replace("[ri_details:", "").replace("]", "").split(":", 1)
        category_key = parts[0] 
        place_name = parts[1]
        
        item = None
        is_rest = category_key.startswith("cat_")
        
        if is_rest:
            real_key = category_key.replace("cat_", "")
            item = next((i for i in RESTAURANTS.get(real_key, []) if i["name"] == place_name), None)
        else:
            real_key = category_key.replace("attr_", "")
            item = next((i for i in ATTRACTIONS.get(real_key, []) if i["name"] == place_name), None)

        if item:
            answer = f"**{item['name']}**\n\n{item['full_desc']}\n\n📍 {item['address']}\n🕒 {item['hours']}\n"
            if is_rest: answer += f"💰 Чек: {item['avg_check']}\n"
            else: answer += f"💰 {item['price']}\n"
            answer += f"⭐ Рейтинг: {item['rating']}"
            
            current_interest = facts.get("current_route_interest", "mix")
            route = DEMO_INTEREST_ROUTES.get(current_interest)
            
            buttons = []
            if route:
                for step in route["steps"]:
                    name_part = step.get('place', step['text'].split('—')[1].split('(')[0].strip())
                    buttons.append({"label": f"📖 {name_part}", "action": step['action']})
                
                first_place_name = route['steps'][0].get('place', route['steps'][0]['text'].split('—')[1].split('(')[0].strip())
                buttons.append({"label": "📍 Всё круто, веди меня", "action": f"[route:walk:{first_place_name}]"})
            
            return {"answer": answer, "action": "none", "image": item["image"], "buttons": buttons}

    if user_text == "[delivery_start]":
        return {"answer": "Отличный выбор! Что будем заказывать?", "action": "none", "buttons": [{"label": "🍕 Пицца", "action": "[delivery_pizza]"}, {"label": "🍣 Роллы", "action": "[delivery_sushi]"}, {"label": "🛒 Продукты", "action": "[delivery_grocery]"}]}
    if user_text.startswith("[delivery_"):
        key = user_text.replace("[delivery_", "").replace("]", "")
        place = DELIVERY_PLACES.get(key)
        if place: return {"answer": f"{place['text']}", "action": "show_card", "card": {"type": "food", "title": place["title"], "text": "Доставка до двери", "button": "Открыть сайт", "url": place["url"]}}

    if user_text == "[housing_start]":
        return {"answer": "Отлично! Выбирай, где остановиться:", "action": "none", "buttons": [{"label": "🏨 Отели", "action": "[housing_hotels]"}, {"label": "🏠 Квартиры посуточно", "action": "[housing_apartments]"}]}

    if user_text == "[housing_hotels]":
        cards = []
        for item in HOTELS:
            taxi_label = "🚗 На авто" if transport == "машина" else "🚕 Такси"
            action_type = "auto" if transport == "машина" else "taxi"
            cards.append({
                "title": item["name"],
                "desc": f"{item['desc']}\n📍 {item['address']}\n💰 {item['avg_check']}\n⭐ {item['rating']}",
                "image": item["image"],
                "buttons": [
                    {"label": "📖 Подробнее", "action": f"[details_hotel:{item['name']}]"},
                    {"label": "🏠 Сделать моим адресом", "action": f"[set_home:{item['name']}]"},
                    {"label": taxi_label, "action": f"[route:{action_type}:{item['coords'][0]},{item['coords'][1]}:{item['name']}]"}
                ]
            })
        return {"answer": "Вот проверенные отели Уфы:", "action": "show_cards", "cards": cards, "buttons": [{"label": "🏨 Все отели", "action": "[housing_hotels]"}, {"label": "🏠 Квартиры", "action": "[housing_apartments]"}]}

    if user_text == "[housing_apartments]":
        cards = []
        for item in APARTMENTS:
            taxi_label = "🚗 На авто" if transport == "машина" else "🚕 Такси"
            action_type = "auto" if transport == "машина" else "taxi"
            cards.append({
                "title": item["name"],
                "desc": f"{item['desc']}\n📍 {item['address']}\n💰 {item['avg_check']}\n⭐ {item['rating']}",
                "image": item["image"],
                "buttons": [
                    {"label": "📞 Позвонить", "action": f"[call_phone:{item['phone']}]", "type": "url"},
                    {"label": "💬 WhatsApp", "action": f"https://wa.me/{item['phone'].replace('+','')}", "type": "url"},
                    {"label": "🏠 Сделать моим адресом", "action": f"[set_home:{item['name']}]"},
                    {"label": taxi_label, "action": f"[route:{action_type}:{item['coords'][0]},{item['coords'][1]}:{item['name']}]"}
                ]
            })
        return {"answer": "Вот квартиры от хозяев:", "action": "show_cards", "cards": cards, "buttons": [{"label": "🏨 Отели", "action": "[housing_hotels]"}, {"label": "🏠 Все квартиры", "action": "[housing_apartments]"}]}

    if user_text.startswith("[call_phone:"):
        phone = user_text.replace("[call_phone:", "").replace("]", "")
        return {"answer": f"Набираю номер: {phone}", "action": "open_url", "url": f"tel:{phone}"}

    if user_text.startswith("[details_hotel:"):
        name = user_text.replace("[details_hotel:", "").replace("]", "")
        item = next((i for i in HOTELS if i["name"] == name), None)
        if item:
            taxi_label = "🚗 На авто" if transport == "машина" else "🚕 Такси"
            action_type = "auto" if transport == "машина" else "taxi"
            return {"answer": f"**{item['name']}**\n\n{item['full_desc']}\n\n📍 {item['address']}\n💰 {item['avg_check']}\n⭐ {item['rating']}", "action": "none", "image": item["image"], "buttons": [
                {"label": "📞 Позвонить", "action": f"[call_phone:{item['phone']}]", "type": "url"},
                {"label": "🏠 Сделать моим адресом", "action": f"[set_home:{item['name']}]"},
                {"label": taxi_label, "action": f"[route:{action_type}:{item['coords'][0]},{item['coords'][1]}:{item['name']}]"}
            ]}

    if user_text == "[food_start]":
        return {"answer": "Кушать подано! Что тебе сейчас по душе?", "action": "none", "buttons": [
            {"label": "🥘 Национальная", "action": "[cat_national]"}, 
            {"label": "☕ Кофе", "action": "[cat_coffee]"}, 
            {"label": "🍔 Бюджетно", "action": "[cat_budget]"}, 
            {"label": "🍷 Премиум", "action": "[cat_premium]"}, 
            {"label": "👨‍👩‍👧‍👦 С детьми", "action": "[cat_kids]"}
        ]}

    if user_text.startswith("[cat_"):
        key = user_text.replace("[cat_", "").replace("]", "")
        items = RESTAURANTS.get(key, [])
        if items:
            cards = []
            for item in items:
                taxi_label = "🚗 На авто" if transport == "машина" else "🚕 Такси"
                action_type = "auto" if transport == "машина" else "taxi"
                cards.append({
                    "title": item["name"],
                    "desc": f"{item['desc']}\n📍 {item['address']}\n🕒 {item['hours']}\n💰 Чек: {item['avg_check']}\n⭐ Рейтинг: {item['rating']}",
                    "image": item["image"],
                    "buttons": [
                        {"label": "📖 Подробнее", "action": f"[details_rest:{key}:{item['name']}]"},
                        {"label": taxi_label, "action": f"[route:{action_type}:{item['coords'][0]},{item['coords'][1]}:{item['name']}]"},
                        {"label": "🚌 Автобус", "action": f"[route:bus:{item['coords'][0]},{item['coords'][1]}:{item['name']}]"},
                        {"label": "🚶 Пешком", "action": f"[route:walk:{item['coords'][0]},{item['coords'][1]}:{item['name']}]"}
                    ]
                })
            
            nav_buttons = [
                {"label": "🥘 Национальная", "action": "[cat_national]"},
                {"label": "☕ Кофе", "action": "[cat_coffee]"},
                {"label": "🍔 Бюджетно", "action": "[cat_budget]"},
                {"label": "🍷 Премиум", "action": "[cat_premium]"},
                {"label": "👨‍👩‍👧‍👦 С детьми", "action": "[cat_kids]"}
            ]
            return {"answer": "Вот лучшие варианты:", "action": "show_cards", "cards": cards, "buttons": nav_buttons}

    if user_text.startswith("[attr_"):
        key = user_text.replace("[attr_", "").replace("]", "")
        items = ATTRACTIONS.get(key, [])
        if items:
            cards = []
            for item in items:
                taxi_label = "🚗 На авто" if transport == "машина" else "🚕 Такси"
                action_type = "auto" if transport == "машина" else "taxi"
                cards.append({
                    "title": item["name"],
                    "desc": f"{item['desc']}\n📍 {item['address']}\n🕒 {item['hours']}\n💰 {item['price']}\n⭐ Рейтинг: {item['rating']}",
                    "image": item["image"],
                    "buttons": [
                        {"label": "📖 Подробнее", "action": f"[details_attr:{key}:{item['name']}]"},
                        {"label": taxi_label, "action": f"[route:{action_type}:{item['coords'][0]},{item['coords'][1]}:{item['name']}]"},
                        {"label": "🚌 Автобус", "action": f"[route:bus:{item['coords'][0]},{item['coords'][1]}:{item['name']}]"},
                        {"label": "🚶 Пешком", "action": f"[route:walk:{item['coords'][0]},{item['coords'][1]}:{item['name']}]"}
                    ]
                })
            nav_buttons = [
                {"label": "🏛 История и музеи", "action": "[attr_history]"},
                {"label": "🌳 Природа и парки", "action": "[attr_nature]"},
                {"label": "🐎 Символы города", "action": "[attr_symbols]"}
            ]
            return {"answer": "Вот что стоит увидеть:", "action": "show_cards", "cards": cards, "buttons": nav_buttons}

    if user_text.startswith("[details_attr:"):
        parts = user_text.replace("[details_attr:", "").replace("]", "").split(":", 1)
        key, name = parts[0], parts[1]
        item = next((i for i in ATTRACTIONS.get(key, []) if i["name"] == name), None)
        if item:
            taxi_label = "🚗 На авто" if transport == "машина" else "🚕 Такси"
            action_type = "auto" if transport == "машина" else "taxi"
            return {"answer": f"**{item['name']}**\n\n{item['full_desc']}\n\n📍 {item['address']}\n🕒 {item['hours']}\n💰 {item['price']}\n⭐ Рейтинг: {item['rating']}", "action": "none", "image": item["image"], "buttons": [
                {"label": taxi_label, "action": f"[route:{action_type}:{item['coords'][0]},{item['coords'][1]}:{item['name']}]"},
                {"label": "🚌 Автобус", "action": f"[route:bus:{item['coords'][0]},{item['coords'][1]}:{item['name']}]"},
                {"label": "🚶 Пешком", "action": f"[route:walk:{item['coords'][0]},{item['coords'][1]}:{item['name']}]"}
            ]}

    if user_text.startswith("[details_rest:"):
        parts = user_text.replace("[details_rest:", "").replace("]", "").split(":", 1)
        key, name = parts[0], parts[1]
        item = next((i for i in RESTAURANTS.get(key, []) if i["name"] == name), None)
        if item:
            taxi_label = "🚗 На авто" if transport == "машина" else "🚕 Такси"
            action_type = "auto" if transport == "машина" else "taxi"
            return {"answer": f"**{item['name']}**\n\n{item['full_desc']}\n\n📍 {item['address']}\n🕒 {item['hours']}\n💰 Чек: {item['avg_check']}\n⭐ Рейтинг: {item['rating']}", "action": "none", "image": item["image"], "buttons": [
                {"label": taxi_label, "action": f"[route:{action_type}:{item['coords'][0]},{item['coords'][1]}:{item['name']}]"},
                {"label": "🚌 Автобус", "action": f"[route:bus:{item['coords'][0]},{item['coords'][1]}:{item['name']}]"},
                {"label": "🚶 Пешком", "action": f"[route:walk:{item['coords'][0]},{item['coords'][1]}:{item['name']}]"}
            ]}

    if user_text.startswith("[route:"):
        clear_pending()
        raw_parts = user_text.replace("[route:", "").replace("]", "").split(":", 2)
        mode = raw_parts[0]
        if len(raw_parts) == 3:
            coords = raw_parts[1].split(",")
            name = raw_parts[2]
        elif len(raw_parts) == 2:
            name = raw_parts[1]
            coords = None
        else:
            return {"answer": "Не понял маршрут", "action": "none"}

        if name == "Памятник Ленину перед Горсоветом":
            return {"answer": "Ты уже на месте! Памятник Ленину прямо перед тобой. Осмотрись и напиши 'Дальше'.", "action": "none"}

        route_data = DEMO_ROUTES.get(name)
        if route_data and mode in route_data:
            steps = route_data[mode]
            save_pending("guide_route", f"{name}|{mode}|0")
            return {"answer": f"Отлично, я поведу тебя за руку до {name}. Шаг 1: {steps[0]}\n\nНапиши 'Дальше', когда выполнишь.", "action": "none"}

        if mode in ["taxi", "auto"]:
            loc_str = facts.get("current_location", "")
            if not loc_str:
                if coords:
                    save_pending("wait_geo", f"{coords[0]},{coords[1]}:{name}")
                else:
                    save_pending("wait_geo", name)
                return {"answer": f"Чтобы построить маршрут до {name}, нажми на компас 🧭", "action": "none"}
            
            start_lat, start_lon = map(float, loc_str.split(','))
            if coords:
                end_lat, end_lon = float(coords[0]), float(coords[1])
            else:
                end_lat, end_lon = geocode_address(name + ", Уфа")

            if end_lat:
                if transport == "машина" or mode == "auto":
                    url = get_auto_map_link(start_lat, start_lon, end_lat, end_lon)
                    return {"answer": f"Автомаршрут до {name} построен.", "action": "show_card", "card": {"type": "map", "title": "🚗 На авто", "text": name, "button": "Открыть Карты", "url": url}}
                else:
                    url = get_taxi_link(start_lat, start_lon, end_lat, end_lon)
                    return {"answer": f"Маршрут до {name} построен.", "action": "show_card", "card": {"type": "taxi", "title": "🚕 Яндекс.Го", "text": name, "button": "Открыть Яндекс Go", "url": url}}
            return {"answer": "Не могу найти адрес.", "action": "none"}

        else: 
            loc_str = facts.get("current_location", "")
            if not loc_str:
                if coords:
                    save_pending("wait_geo", f"{coords[0]},{coords[1]}:{name}")
                else:
                    save_pending("wait_geo", name)
                return {"answer": "Сначала нажми на компас 🧭, чтобы я знал, откуда ехать.", "action": "none"}
            
            start_lat, start_lon = map(float, loc_str.split(','))
            if coords:
                end_lat, end_lon = float(coords[0]), float(coords[1])
            else:
                end_lat, end_lon = geocode_address(name + ", Уфа")

            if end_lat:
                if mode == "bus":
                    url = get_bus_map_link(start_lat, start_lon, end_lat, end_lon)
                    title = "🚌 Общественный транспорт"
                else:
                    url = get_walk_map_link(start_lat, start_lon, end_lat, end_lon)
                    title = "🚶 Пешеходный маршрут"
                    
                return {"answer": f"Маршрут до {name} построен. Открывай Яндекс.Карты.", "action": "show_card", "card": {"type": "map", "title": title, "text": name, "button": "Открыть Карты", "url": url}}
            return {"answer": "Не могу найти адрес.", "action": "none"}

    if user_text.startswith("[transport:"):
        parts = user_text.replace("[transport:", "").replace("]", "").split(":", 1)
        mode = parts[0]
        name = parts[1] if len(parts) > 1 else "Место"
        
        end_lat, end_lon = geocode_address(name + ", Уфа")
        
        if mode in ["taxi", "auto"] and end_lat:
            loc_str = facts.get("current_location", "")
            if not loc_str:
                save_pending("wait_geo", f"{end_lat},{end_lon}:{name}")
                return {"answer": f"Чтобы построить маршрут до {name}, нажми на компас 🧭", "action": "none"}
            start_lat, start_lon = map(float, loc_str.split(','))
            
            if transport == "машина" or mode == "auto":
                url = get_auto_map_link(start_lat, start_lon, end_lat, end_lon)
                return {"answer": f"Автомаршрут до {name} построен.", "action": "show_card", "card": {"type": "map", "title": "🚗 На авто", "text": name, "button": "Открыть Карты", "url": url}}
            else:
                url = get_taxi_link(start_lat, start_lon, end_lat, end_lon)
                return {"answer": f"Маршрут до {name} построен.", "action": "show_card", "card": {"type": "taxi", "title": "🚕 Яндекс.Го", "text": name, "button": "Открыть Яндекс Go", "url": url}}
        
        elif mode == "bus":
            route_data = DEMO_ROUTES.get(name)
            if route_data and "bus" in route_data:
                steps = route_data["bus"]
                save_pending("guide_route", f"{name}|bus|0")
                return {"answer": f"Отлично, я поведу тебя за руку до {name}. Шаг 1: {steps[0]}\n\nНапиши 'Дальше', когда выполнишь.", "action": "none"}
            else:
                if end_lat:
                    loc_str = facts.get("current_location", "")
                    if not loc_str:
                        save_pending("wait_geo", f"{end_lat},{end_lon}:{name}")
                        return {"answer": f"Чтобы построить маршрут до {name}, нажми на компас 🧭", "action": "none"}
                    start_lat, start_lon = map(float, loc_str.split(','))
                    url = get_bus_map_link(start_lat, start_lon, end_lat, end_lon)
                    return {"answer": f"Маршрут на автобусе до {name} построен. Открывай Яндекс.Карты.", "action": "show_card", "card": {"type": "map", "title": "🚌 Общественный транспорт", "text": name, "button": "Открыть Карты", "url": url}}
                return {"answer": "Не могу найти адрес. Попробуй иначе.", "action": "none"}
        
        elif mode == "walk":
            route_data = DEMO_ROUTES.get(name)
            if route_data and "walk" in route_data:
                steps = route_data["walk"]
                save_pending("guide_route", f"{name}|walk|0")
                return {"answer": f"Отлично, я поведу тебя за руку до {name}. Шаг 1: {steps[0]}\n\nНапиши 'Дальше', когда выполнишь.", "action": "none"}
            else:
                if end_lat:
                    loc_str = facts.get("current_location", "")
                    if not loc_str:
                        save_pending("wait_geo", f"{end_lat},{end_lon}:{name}")
                        return {"answer": f"Чтобы построить маршрут до {name}, нажми на компас 🧭", "action": "none"}
                    start_lat, start_lon = map(float, loc_str.split(','))
                    url = get_walk_map_link(start_lat, start_lon, end_lat, end_lon)
                    return {"answer": f"Пешеходный маршрут до {name} построен. Открывай Яндекс.Карты.", "action": "show_card", "card": {"type": "map", "title": "🚶 Пешком", "text": name, "button": "Открыть Карты", "url": url}}
                return {"answer": "Не могу найти адрес. Попробуй иначе.", "action": "none"}

    pending = get_pending()
    if pending and pending.get("action") == "wait_transport_choice":
        dest_data = pending.get("params")
        if ":" in dest_data:
            coords_str, dest_name = dest_data.split(":", 1)
        else:
            coords_str = None
            dest_name = dest_data

        mode = None
        if any(w in text_lower for w in ["такси", "машин", "авто", "го"]):
            mode = "auto" if transport == "машина" else "taxi"
        elif any(w in text_lower for w in ["автобус", "обществен", "маршрутк"]):
            mode = "bus"
        elif any(w in text_lower for w in ["пеш", "ногах", "идти", "пройти"]):
            mode = "walk"

        if mode:
            clear_pending()
            loc_str = facts.get("current_location", "")
            if not loc_str: return {"answer": "Нажми на компас 🧭", "action": "none"}
            
            start_lat, start_lon = map(float, loc_str.split(','))
            if coords_str:
                end_lat, end_lon = map(float, coords_str.split(','))
            else:
                end_lat, end_lon = geocode_address(dest_name + ", Уфа")

            if mode in ["taxi", "auto"]:
                if mode == "auto" or transport == "машина":
                    url = get_auto_map_link(start_lat, start_lon, end_lat, end_lon)
                    return {"answer": f"Автомаршрут до {dest_name} построен.", "action": "show_card", "card": {"type": "map", "title": "🚗 На авто", "text": dest_name, "button": "Открыть Карты", "url": url}}
                else:
                    url = get_taxi_link(start_lat, start_lon, end_lat, end_lon)
                    return {"answer": f"Маршрут до {dest_name} построен.", "action": "show_card", "card": {"type": "taxi", "title": "🚕 Яндекс.Го", "text": dest_name, "button": "Открыть Яндекс Go", "url": url}}
            elif mode == "bus":
                url = get_bus_map_link(start_lat, start_lon, end_lat, end_lon)
                return {"answer": f"Маршрут на автобусе до {dest_name} построен.", "action": "show_card", "card": {"type": "map", "title": "🚌 Общественный транспорт", "text": dest_name, "button": "Открыть Карты", "url": url}}
            elif mode == "walk":
                url = get_walk_map_link(start_lat, start_lon, end_lat, end_lon)
                return {"answer": f"Пешеходный маршрут до {dest_name} построен.", "action": "show_card", "card": {"type": "map", "title": "🚶 Пешком", "text": dest_name, "button": "Открыть Карты", "url": url}}
        else:
            btns = []
            if coords_str:
                btns = [
                    {"label": "🚕 Такси", "action": f"[route:taxi:{coords_str}:{dest_name}]"},
                    {"label": "🚗 На авто", "action": f"[route:auto:{coords_str}:{dest_name}]"},
                    {"label": "🚌 Автобус", "action": f"[route:bus:{coords_str}:{dest_name}]"},
                    {"label": "🚶 Пешком", "action": f"[route:walk:{coords_str}:{dest_name}]"}
                ]
            return {"answer": "Слушай, я не понял, как ты хочешь поехать. Выбери кнопку ниже или напиши 'такси', 'автобус' или 'пешком'.", "action": "none", "buttons": btns}

    if "home_address" in facts:
        if any(word in text_lower for word in ["поесть", "голоден", "ресторан", "кафе", "перекусить", "хочу есть", "кушать", "еда"]):
            return {"answer": "Кушать подано! Что тебе сейчас по душе?", "action": "none", "buttons": [{"label": "🥘 Национальная", "action": "[cat_national]"}, {"label": "☕ Кофе", "action": "[cat_coffee]"}, {"label": "🍔 Бюджетно", "action": "[cat_budget]"}, {"label": "🍷 Премиум", "action": "[cat_premium]"}, {"label": "👨‍👩‍👧‍👦 С детьми", "action": "[cat_kids]"}]}

        if any(word in text_lower for word in ["жить", "жилье", "жильё", "гостиниц", "отель", "квартир", "снять", "переночевать", "устал", "где поспать", "где остановиться"]):
            return {"answer": "Понял, тебе нужно жильё. Вот варианты:", "action": "none", "buttons": [{"label": "🏨 Отели", "action": "[housing_hotels]"}, {"label": "🏠 Квартиры посуточно", "action": "[housing_apartments]"}]}

        if any(word in text_lower for word in ["экскурси", "что посмотреть", "куда сходить", "куда съездить", "где погулять", "достопримечательности", "что есть в уфе", "чем заняться", "что еще", "расскажи про уфу", "хочу посмотреть"]):
            return {"answer": "У нас тут есть всё! А что тебе сейчас больше по душе?", "action": "none", "buttons": [{"label": "🏛 История и музеи", "action": "[attr_history]"}, {"label": "🌳 Природа и парки", "action": "[attr_nature]"}, {"label": "🐎 Символы города", "action": "[attr_symbols]"}]}

    if "name" not in facts or facts.get("name") == "":
        words = re.findall(r'\b[А-Яа-яЁё]{2,}\b', user_text)
        stop_words = ["меня", "зовут", "зови", "это", "ну", "привет", "здравствуйте", "добрый", "день", "вечер", "утро"]
        words = [w for w in words if w.lower() not in stop_words]
        
        if not words:
            return {"answer": "Слушай, напиши просто свое имя (например: Иван).", "action": "none"}
        
        name = words[-1].capitalize()
        
        if len(name) <= 30 and name.lower() not in NAME_BLACKLIST:
            save_fact("name", name)
            return {"answer": RESPONSES["onboarding_ask_city"].format(name=name), "action": "none"}
        return {"answer": "Слушай, напиши просто свое имя (например: Иван).", "action": "none"}

    if "from_city" not in facts or "transport" not in facts:
        city_lower = user_text.lower().strip()
        found_city = None
        city_match = re.search(r'(?:из|с|приехал из|прибыл из)\s+([А-ЯЁ][а-яё]+)', user_text, re.IGNORECASE)
        
        if city_match:
            found_city = city_match.group(1).lower()
        else:
            for core, canonical in CITY_CORES.items():
                if core in city_lower:
                    found_city = canonical
                    break
        
        if found_city:
            save_fact("from_city", found_city.capitalize())
            reaction = CITY_REACTIONS.get(found_city)
            if reaction:
                return {"answer": f"{reaction} А как вы до нас добрались? На поезде, на самолете, на машине или на автобусе?", "action": "none"}
            else:
                return {"answer": RESPONSES["onboarding_ask_transport"].format(city=found_city.capitalize()), "action": "none"}
        
        if "from_city" not in facts:
             return {"answer": "Слушай, а откуда ты к нам приехал? Назови город.", "action": "none"}

    if "transport" not in facts:
        new_transport = None
        if any(w in text_lower for w in ["поезд", "электричк", "жд", "вокзал", "железн", "рельс"]): new_transport = "поезд"
        elif any(w in text_lower for w in ["самолет", "аэропорт", "прилетел", "летел", "борт", "авиа"]): new_transport = "самолет"
        elif any(w in text_lower for w in ["автобус", "автостанц", "маршрутк"]): new_transport = "автобус" 
        elif any(w in text_lower for w in ["машин", "авто", "руле", "водител", "приехал на колесах"]): new_transport = "машина"
        
        if new_transport:
            save_fact("transport", new_transport)
            return {"answer": RESPONSES["onboarding_ask_destination"], "action": "none"}
        else:
            return {"answer": "Не совсем понял. Ты приехал на поезде, на самолете, на машине или на автобусе?", "action": "none"}

    if "home_address" not in facts:
        if any(w in text_lower for w in ["сюда", "туда", "поедем", "поехали", "давай", "выбрал"]) and len(user_text.split()) < 6:
             return {"answer": "Я не совсем поняла, куда именно. Назови точный адрес, отель или место.", "action": "none"}

        clean_text_for_address = user_text.replace(',', ' ')
        clean_words = [w for w in clean_text_for_address.split() if w.lower() not in ["нет", "мне", "нужно", "пожалуйста", "хочу", "поехали", "поедем", "давай"]]
        clean_address = " ".join(clean_words).strip()
        
        if len(clean_address) < 2:
            clean_address = user_text

        save_fact("home_address", clean_address)
        transport = facts.get("transport", "неизвестно")
        care_msg = ""
        
        if transport == "машина": 
            care_msg = "По пути следования будет заправка Лукойл, советую заправиться, если бак пустой."
        elif transport == "поезд": 
            care_msg = "Кстати, рядом с вашим адресом есть круглосуточный магазин 'Купец', если проголодались."
        
        if transport == "машина":
            if not facts.get("current_location"):
                save_pending("wait_geo", clean_address)
                return {"answer": f"Отлично, запомнила: {clean_address}. {care_msg} Нажми на компас 🧭, чтобы я построила маршрут.", "action": "none"}
            
            loc = facts.get("current_location").split(',')
            end_lat, end_lon = geocode_address(clean_address + ", Уфа")
            if end_lat:
                url = get_auto_map_link(float(loc[0]), float(loc[1]), end_lat, end_lon)
                return {"answer": f"Отлично! {care_msg} Автомаршрут до {clean_address} построен.", "action": "show_card", "card": {"type": "map", "title": "🚗 На авто", "text": clean_address, "button": "Открыть Карты", "url": url}}
            else:
                return {"answer": "Запомнила адрес, но не вижу тебя. Нажми на компас 🧭!", "action": "none"}
        else:
            save_pending("wait_transport_choice", clean_address)
            return {"answer": f"Отлично, запомнила: {clean_address}. {care_msg} А на чем поедем до отеля?", "action": "none", "buttons": [{"label": "🚕 Такси", "action": f"[transport:taxi:{clean_address}]"}, {"label": "🚌 Автобус", "action": f"[transport:bus:{clean_address}]"}, {"label": "🚶 Пешком", "action": f"[transport:walk:{clean_address}]"}]}

    if any(word in text_lower for word in ["домой", "дом", "обратно", "в отель"]):
        loc_str = facts.get("current_location", "")
        if not loc_str: 
            save_pending("wait_geo", "домой")
            return {"answer": "Я не знаю, где ты. Нажми на компас 🧭, чтобы я нашла тебя.", "action": "none"}
        saved_addr = facts.get("home_address")
        if saved_addr:
            start_lat, start_lon = map(float, loc_str.split(','))
            end_lat, end_lon = geocode_address(saved_addr + ", Уфа")
            if end_lat:
                if transport == "машина":
                    url = get_auto_map_link(start_lat, start_lon, end_lat, end_lon)
                    return {"answer": f"Автомаршрут до дома построен.", "action": "show_card", "card": {"type": "map", "title": "🚗 На авто", "text": saved_addr, "button": "Открыть Карты", "url": url}}
                else:
                    url = get_taxi_link(start_lat, start_lon, end_lat, end_lon)
                    return {"answer": f"Маршрут до дома построен. Кстати, голодны? Могу заказать доставку прямо к двери.", "action": "show_card", "card": {"type": "taxi", "title": "🚕 Яндекс.Го", "text": saved_addr, "button": "Открыть Яндекс Go", "url": url}, "buttons": [{"label": "🍕 Заказать доставку", "action": "[delivery_start]"}]}
        save_pending("ask_home_address", "")
        return {"answer": "А где ты остановился? Назови отель или точный адрес.", "action": "none"}

    pending = get_pending()
    if pending and pending.get("action") == "ask_home_address":
        clear_pending()
        save_fact("home_address", user_text)
        loc_str = facts.get("current_location", "")
        if loc_str:
            start_lat, start_lon = map(float, loc_str.split(','))
            end_lat, end_lon = geocode_address(user_text + ", Уфа")
            if end_lat:
                if transport == "машина":
                    url = get_auto_map_link(start_lat, start_lon, end_lat, end_lon)
                    return {"answer": f"Отлично, запомнила: {user_text}. Автомаршрут построен!", "action": "show_card", "card": {"type": "map", "title": "🚗 На авто", "text": user_text, "button": "Открыть Карты", "url": url}}
                else:
                    url = get_taxi_link(start_lat, start_lon, end_lat, end_lon)
                    return {"answer": f"Отлично, запомнила: {user_text}. Маршрут построен!", "action": "show_card", "card": {"type": "taxi", "title": "🚕 Яндекс.Го", "text": user_text, "button": "Открыть Яндекс Go", "url": url}}
        return {"answer": "Адрес записала, но я не вижу, где ты. Нажми на компас 🧭!", "action": "none"}

    try:
        loop = asyncio.get_running_loop()
        intent = await loop.run_in_executor(None, ask_uje_router, user_text, facts, message.history)
        for k, v in intent.get("new_facts", {}).items(): save_fact(k, v)
        
        if intent.get("action") == "call_taxi":
            dest = intent.get("params", {}).get("destination", "").strip()
            if dest:
                loc_str = facts.get("current_location", "")
                if not loc_str: 
                    save_pending("wait_geo", dest)
                    return {"answer": "Сначала нажми на компас 🧭, чтобы я знала, откуда ехать.", "action": "none"}
                start_lat, start_lon = map(float, loc_str.split(','))
                end_lat, end_lon = geocode_address(dest + ", Башкортостан")
                if end_lat:
                    if transport == "машина":
                        url = get_auto_map_link(start_lat, start_lon, end_lat, end_lon)
                        return {"answer": f"Автомаршрут построен: {dest}.", "action": "show_card", "card": {"type": "map", "title": "🚗 На авто", "text": dest, "button": "Открыть Карты", "url": url}}
                    else:
                        url = get_taxi_link(start_lat, start_lon, end_lat, end_lon)
                        return {"answer": f"Маршрут построен: {dest}.", "action": "show_card", "card": {"type": "taxi", "title": "🚕 Яндекс.Го", "text": dest, "button": "Открыть Яндекс Go", "url": url}}
            return {"answer": "Куда едем?", "action": "none"}
        
        reply_text = intent.get("params", {}).get("reply", "").strip()
        if not reply_text:
            reply_text = await loop.run_in_executor(None, ask_gpt_free, user_text, message.history)
        
        return {"answer": reply_text or "Слушай, я тут немного задумалась, но давай попробуем еще раз?", "action": "none"}
        
    except Exception as e:
        try:
            loop = asyncio.get_running_loop()
            fallback_reply = await loop.run_in_executor(None, ask_gpt_free, user_text, message.history)
            return {"answer": fallback_reply or "Я на связи, но у меня тут небольшие помехи. Попробуй еще раз!", "action": "none"}
        except:
            return {"answer": "У меня тут небольшие помехи. Давай еще раз попробуем?", "action": "none"}