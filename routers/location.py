# routers/location.py
from fastapi import APIRouter, Request
from pydantic import BaseModel

from memory import save_fact, get_pending, clear_pending, log_event
from tools import current_zone, geocode_address

router = APIRouter()

class LocationData(BaseModel):
    lat: float
    lon: float

# Словарь человекочитаемых названий зон вместо технических ID
ZONE_NAMES = {
    "ufa_center": "в центре Уфы",
    "ufa": "в Уфе",
    "sterlitamak": "в Стерлитамаке",
    "pavlovka": "в районе Павловки",
    "bashkortostan": "в Башкирии",
}

@router.post("/api/location")
async def receive_location(data: LocationData, request: Request):
    sid = getattr(request.state, "session_id", "anon_default")
    
    zone = current_zone(data.lat, data.lon)
    save_fact(sid, "current_location", f"{data.lat},{data.lon}")
    save_fact(sid, "current_zone", zone)
    log_event(sid, "geo_received", {"zone": zone})
    
    # Получаем читаемое название вместо технического ID
    zone_text = ZONE_NAMES.get(zone, "в Башкирии")
    
    pending = get_pending(sid)
    
    # Ветка 1: Ждём адрес для такси/авто после [call_taxi_start] или wait_geo
    if pending and pending.get("action") == "wait_geo":
        raw_params = pending.get("params", "")
        clear_pending(sid)
        
        # Парсим параметры: может быть просто имя или "lat,lon:name"
        if ":" in raw_params and "," in raw_params.split(":")[0]:
            try:
                coords_part, dest_name = raw_params.split(":", 1)
                end_lat, end_lon = map(float, coords_part.split(","))
            except ValueError:
                end_lat, end_lon = None, None
                dest_name = raw_params
        else:
            end_lat, end_lon = None, None
            dest_name = raw_params
            
        if not end_lat:
            end_lat, end_lon = geocode_address(dest_name + ", Уфа")
            
        if end_lat:
            # Отправляем кнопки с координатами внутри action, чтобы chat.py не гадал
            return {
                "status": "ok", 
                "zone": zone, 
                "action": "none",
                "answer": f"Отлично, вижу тебя! Как поедем до {dest_name}?",
                "buttons": [
                    {"label": "🚕 Такси", "action": f"[route:taxi:{end_lat},{end_lon}:{dest_name}]"},
                    {"label": "🚗 На авто", "action": f"[route:auto:{end_lat},{end_lon}:{dest_name}]"},
                    {"label": "🚌 Автобус", "action": f"[route:bus:{dest_name}]"},
                    {"label": "🚶 Пешком", "action": f"[route:walk:{dest_name}]"}
                ]
            }
        else:
            return {
                "status": "ok", 
                "zone": zone, 
                "action": "none",
                "answer": f"Вижу тебя {zone_text}, но не могу найти адрес '{dest_name}'. Попробуй назвать точнее.",
                "buttons": []
            }

    # Ветка 2: Выбор транспорта после ввода адреса в онбординге
    if pending and pending.get("action") == "wait_transport_choice":
        dest_name = pending.get("params")
        clear_pending(sid)
        return {
            "status": "ok", 
            "zone": zone, 
            "action": "none", 
            "answer": f"Отлично, вижу, что ты {zone_text}. На чем поедем до {dest_name}?",
            "buttons": [
                {"label": "🚕 Такси", "action": f"[transport:taxi:{dest_name}]"},
                {"label": "🚌 Автобус", "action": f"[transport:bus:{dest_name}]"},
                {"label": "🚶 Пешком", "action": f"[transport:walk:{dest_name}]"}
            ]
        }
    
    # Ветка 3: Просто геолокация без активного ожидания
    return {
        "status": "ok", 
        "zone": zone, 
        "action": "none", 
        "answer": f"Отлично, вижу, что ты {zone_text}. Куда нужно построить маршрут? Назови место или нажми кнопку ниже."
    }