from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse # <--- НОВОЕ
from pydantic import BaseModel
import uvicorn
import asyncio
from concurrent.futures import ThreadPoolExecutor
from ai_brain import ask_uje_router
from memory import init_db, save_fact, get_all_facts
from tools import get_weather, call_taxi, check_bus, play_music, order_food

app = FastAPI()
templates = Jinja2Templates(directory="templates")
executor = ThreadPoolExecutor(max_workers=4)

# ... (твой класс UserMessage и LocationData) ...

@app.get("/manifest.json")
async def get_manifest():
    return FileResponse("manifest.json")

@app.get("/sw.js")
async def get_sw():
    return FileResponse("sw.js")

# ... (остальной код ask_bot без изменений) ...