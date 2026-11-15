from fastapi import APIRouter, Response
from pydantic import BaseModel
import re, os, requests
from memory import get_all_facts

router = APIRouter()

class TTSRequest(BaseModel):
    text: str

@router.post("/api/tts")
async def text_to_speech(req: TTSRequest):
    facts = get_all_facts()
    guide = facts.get("guide_gender", "female")
    voice = "filipp" if guide == "male" else "alena"

    clean_text = re.sub(r'[*#_~`®©]', '', re.sub(r'[\U00010000-\U0010ffff]', '', req.text)).strip()
    if not clean_text: return Response(status_code=400)
    
    folder_id, api_key = os.getenv("YC_FOLDER_ID"), os.getenv("YC_API_KEY")
    if not api_key or not folder_id: return Response(status_code=500)
    
    try:
        res = requests.post(
            "https://tts.api.yandex.net/speech/v1/tts:synthesize", 
            headers={"Authorization": f"Api-Key {api_key}"}, 
            data={"text": clean_text[:1000], "lang": "ru-RU", "voice": voice, "folderId": folder_id, "format": "mp3", "speed": "1.0"}, 
            timeout=10
        )
        return Response(content=res.content, media_type="audio/mpeg") if res.status_code == 200 else Response(status_code=500)
    except: 
        return Response(status_code=500)