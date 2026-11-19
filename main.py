# main.py
import io
import os
import asyncio
import csv
import hashlib
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request, UploadFile, File, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# Импорт модулей проекта
from memory import (
    init_db, save_fact, get_all_facts, save_pending, get_pending, 
    clear_pending, clear_all_facts, log_event, export_events_csv, 
    save_lead, get_leads
)
from tools import (
    get_real_weather, get_taxi_link, get_auto_map_link, get_bus_map_link, get_walk_map_link,
    get_news_ufa, get_currency, get_traffic, current_zone, geocode_address, 
    RESTAURANTS, ATTRACTIONS, HOTELS, APARTMENTS, DELIVERY_PLACES, DEMO_ROUTES, DEMO_INTEREST_ROUTES
)
from responses import RESPONSES, FACT_LABELS, DEFAULT_QUICK_ACTIONS, NAME_BLACKLIST, CITY_CORES, CITY_REACTIONS
from ai_brain import generate_briefing, analyze_file_text
from data.config import ASSET_VERSION
from data.places import MAP_POIS
from routers.chat import router as chat_router
from routers.tts import router as tts_router
from routers.location import router as location_router

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(lifespan=lifespan)

# Middleware для получения session_id из заголовка или cookie
@app.middleware("http")
async def add_session_id(request: Request, call_next):
    sid = request.headers.get("X-Session-Id") or request.cookies.get("bashgid_sid")
    if not sid:
        sid = "anon_default" 
    
    request.state.session_id = sid
    
    response = await call_next(request)
    
    # Устанавливаем куку при первом обращении, если её не было
    if sid == "anon_default":
        response.set_cookie(key="bashgid_sid", value=sid, httponly=True, max_age=86400*30)
        
    return response

app.include_router(location_router)
app.include_router(chat_router)
app.include_router(tts_router)
app.mount("/static", StaticFiles(directory="templates"), name="static")
templates = Jinja2Templates(directory="templates")
executor = ThreadPoolExecutor(max_workers=4)

# Вспомогательная функция для получения session_id внутри эндпоинтов
def get_current_session_id(request: Request) -> str:
    return getattr(request.state, "session_id", "anon_default")

class ResetRequest(BaseModel):
    token: Optional[str] = None

@app.post("/api/reset")
async def reset_memory(req: ResetRequest = None, request: Request = None):
    """Сброс данных текущего пользователя. Полный сброс базы требует токена."""
    # Безопасность: если нет request (старый фронт), используем anon
    sid = get_current_session_id(request) if request else "anon_default"
    
    admin_token = os.getenv("ADMIN_RESET_TOKEN", "")
    if req and req.token and admin_token and req.token == admin_token:
        # Грубая очистка файла БД для полного сброса
        db_path = os.path.join(os.path.dirname(__file__), "uje_memory.db")
        if os.path.exists(db_path):
            os.remove(db_path)
        init_db()
        return {"status": "ok", "scope": "global"}
    
    # Обычный сброс профиля текущей сессии
    clear_all_facts(sid)
    return {"status": "ok", "scope": "local"}

@app.get("/")
async def read_root(request: Request):
    """Главная страница приложения."""
    return templates.TemplateResponse(request=request, name="index.html", context={"asset_version": ASSET_VERSION})

@app.get("/manifest.json")
async def get_manifest():
    return JSONResponse({
        "name": "БАШГИД",
        "short_name": "БАШГИД",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#005BBB",
        "theme_color": "#005BBB"
    }, headers={"Cache-Control": "no-cache"})

@app.get("/sw.js")
async def get_sw():
    js_content = f"""const CACHE_NAME = 'bashgid-v{ASSET_VERSION}';
self.addEventListener('install', (e) => {{ self.skipWaiting(); }});
self.addEventListener('activate', (e) => {{ e.waitUntil(caches.keys().then((names) => Promise.all(names.filter((n) => n !== CACHE_NAME).map((n) => caches.delete(n)))).then(() => self.clients.claim())); }});
self.addEventListener('fetch', (e) => {{ e.respondWith(fetch(e.request).catch(() => caches.match(e.request))); }});"""
    return Response(content=js_content, media_type="application/javascript", headers={"Cache-Control": "no-cache"})

@app.get("/api/current_weather")
async def get_current_weather():
    parts = (await asyncio.get_running_loop().run_in_executor(executor, get_real_weather, "Уфа")).split(',')
    return {"temp": parts[0].strip() if parts else "--°", "desc": parts[1].strip() if len(parts) > 1 else ""}

@app.get("/api/map_points")
async def get_map_points():
    return {"points": MAP_POIS}

@app.get("/api/briefing")
async def get_briefing(request: Request):
    loop = asyncio.get_running_loop()
    w = await loop.run_in_executor(executor, get_real_weather, "Уфа")
    n = await loop.run_in_executor(executor, get_news_ufa)
    c = await loop.run_in_executor(executor, get_currency)
    t = get_traffic()
    
    sid = get_current_session_id(request)
    facts = get_all_facts(sid)
    
    text = await loop.run_in_executor(executor, generate_briefing, w, t, c, n, facts.get("name", "друг"))
    return {"answer": text}

@app.get("/api/status")
async def get_status(request: Request):
    sid = get_current_session_id(request)
    facts = get_all_facts(sid)
    
    is_new = len(facts) == 0 or "guide_gender" not in facts
    if is_new:
        return {
            "is_new": True,
            "greeting": "Привет! Я — БашГид, ваш персональный гид по Башкирии. Выбери, с кем продолжишь путь: ",
            "action": "select_guide",
            "placeholder": RESPONSES["input_placeholder_empty"]
        }
    return {
        "is_new": False,
        "greeting": RESPONSES["greeting_return"].format(name=facts.get("name", "гость")),
        "placeholder": RESPONSES["input_placeholder_ready"],
        "quick_actions": DEFAULT_QUICK_ACTIONS
    }

# ===== АНАЛИТИКА ДЛЯ ГОСКОМИТЕТА =====

@app.get("/api/export/events")
async def export_events_api(from_date: str = None, to_date: str = None):
    """Выгрузка событий в CSV для анализа турпотока."""
    events = export_events_csv(from_date, to_date)
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["timestamp", "session_hash", "event_type", "payload"])
    
    for e in events:
        # Хэшируем session_id для анонимизации перед выгрузкой
        hash_sid = hashlib.md5(e['session_id'].encode()).hexdigest()[:8]
        writer.writerow([e['created_at'], hash_sid, e['event_type'], e['payload']])
        
    mem = output.getvalue()
    output.close()
    
    iter_mem = iter(mem.encode('utf-8'))
    return StreamingResponse(iter_mem, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=bashgid_events.csv"})

@app.get("/api/stats/dashboard")
async def dashboard_stats():
    """Простая статистика для дашборда."""
    all_events = export_events_csv()
    
    total_users = len(set(e['session_id'] for e in all_events))
    completed_routes = sum(1 for e in all_events if e['event_type'] == 'route_completed')
    photo_cards_saved = sum(1 for e in all_events if e['event_type'] == 'photo_card_saved')
    
    # Топ мест по посещаемости (парсим payload)
    places_count = {}
    for e in all_events:
        if e['event_type'] == 'route_started':
            try:
                import json
                payload = json.loads(e['payload'])
                place = payload.get('destination', 'Unknown')
                places_count[place] = places_count.get(place, 0) + 1
            except:
                pass
                
    top_places = sorted(places_count.items(), key=lambda x: x[1], reverse=True)[:5]
    
    return {
        "total_unique_sessions": total_users,
        "routes_completed": completed_routes,
        "photos_saved": photo_cards_saved,
        "top_destinations": [{"name": k, "count": v} for k, v in top_places]
    }

# ===== ЛИДЫ (ЗАЯВКИ) =====

class LeadForm(BaseModel):
    name: str
    phone: str
    tour_interest: str = ""
    consent_given: bool = False

@app.post("/api/lead")
async def create_lead(form: LeadForm, request: Request):
    sid = get_current_session_id(request)
    
    if not form.consent_given:
        raise HTTPException(status_code=400, detail="Требуется согласие на обработку персональных данных.")
        
    save_lead(sid, "default_partner", form.name, form.phone, form.tour_interest, form.consent_given)
    log_event(sid, "lead_created", {"tour": form.tour_interest})
    
    return {"status": "ok", "message": "Заявка принята. Менеджер свяжется с вами."}

@app.get("/api/admin/leads")
async def view_leads(admin_key: str = None):
    """Просмотр заявок. Требует ключ администратора."""
    secret = os.getenv("LEADS_VIEW_KEY", "")
    if not secret or admin_key != secret:
        raise HTTPException(status_code=403, detail="Access denied")
        
    leads = get_leads()
    return {"count": len(leads), "data": leads}

# ===== ФАЙЛЫ =====

@app.post("/api/upload")
async def upload_file(request: Request, file: UploadFile = File(...)):
    raw = await file.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        return {"answer": "⚠️ Файл слишком большой.", "action": "none"}
    
    text = ""
    try:
        if file.filename.endswith(".docx"):
            import docx
            text = "\n".join([p.text for p in docx.Document(io.BytesIO(raw)).paragraphs])
        elif file.filename.endswith(".pdf"):
            import PyPDF2
            text = "\n".join([p.extract_text() for p in PyPDF2.PdfReader(io.BytesIO(raw)).pages])
        elif file.filename.endswith(".xlsx") or file.filename.endswith(".csv"):
            import pandas as pd
            df = pd.read_excel(io.BytesIO(raw)) if file.filename.endswith(".xlsx") else pd.read_csv(io.BytesIO(raw))
            text = df.to_string(index=False)
            
        if not text.strip():
            return {"answer": "Файл пустой или не читается.", "action": "none"}
            
        analysis = await asyncio.get_running_loop().run_in_executor(executor, analyze_file_text, text, "user", file.filename)
        return {"answer": analysis, "action": "none"}
        
    except Exception as e:
        return {"answer": f"Ошибка обработки файла: {str(e)}", "action": "none"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)