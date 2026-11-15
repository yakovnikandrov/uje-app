# routers/location.py
from fastapi import APIRouter
from pydantic import BaseModel
from memory import save_fact, save_pending, get_pending, clear_pending
from tools import current_zone, geocode_address

router = APIRouter()

class LocationData(BaseModel):
    lat: float
    lon: float

@router.post("/api/location")
async def receive_location(data: LocationData):
    zone = current_zone(data.lat, data.lon)
    save_fact("current_location", f"{data.lat},{data.lon}")
    save_fact("current_zone", zone)
    
    pending = get_pending()
    if pending and pending.get("action") == "wait_geo":
        clear_pending()
        dest_data = pending.get("params")
        
        if ":" in dest_data:
            coords_str, dest_name = dest_data.split(":", 1)
            end_lat, end_lon = map(float, coords_str.split(","))
        else:
            dest_name = dest_data
            end_lat, end_lon = geocode_address(dest_name + ", Уфа")
        
        if end_lat:
            save_pending("wait_transport_choice", f"{end_lat},{end_lon}:{dest_name}")
            return {
                "status": "ok", "zone": zone, "action": "none", 
                "answer": f"Отлично, вижу тебя! Как поедем до {dest_name}?", 
                "buttons": [
                    {"label": "🚕 Такси", "action": f"[route:taxi:{end_lat},{end_lon}:{dest_name}]"},
                    {"label": "🚗 На авто", "action": f"[route:auto:{end_lat},{end_lon}:{dest_name}]"},
                    {"label": "🚌 Автобус", "action": f"[route:bus:{end_lat},{end_lon}:{dest_name}]"},
                    {"label": "🚶 Пешком", "action": f"[route:walk:{end_lat},{end_lon}:{dest_name}]"}
                ]
            }

    if pending and pending.get("action") == "wait_transport_choice":
        dest_name = pending.get("params")
        return {"status": "ok", "zone": zone, "action": "none", "answer": f"Отлично, вижу, что вы {zone}. На чем поедем до {dest_name}?", "buttons": [{"label": "🚕 Такси", "action": f"[transport:taxi:{dest_name}]"}, {"label": "🚌 Автобус", "action": f"[transport:bus:{dest_name}]"}, {"label": "🚶 Пешком", "action": f"[transport:walk:{dest_name}]"}]}

    return {"status": "ok", "zone": zone, "action": "none", "answer": f"Отлично, вижу, что вы {zone}. Куда вам нужно построить маршрут? Назовите адрес или место, и я проложу путь."}