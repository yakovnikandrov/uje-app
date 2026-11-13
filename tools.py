# tools.py
import requests
import urllib.parse
import re
import random
import time
from math import radians, sin, cos, asin, sqrt

WEATHER_TRANSLATION = {
    "Sunny": "Солнечно", "Clear": "Ясно", "Partly cloudy": "Переменная облачность",
    "Cloudy": "Облачно", "Overcast": "Пасмурно", "Mist": "Туман",
    "Patchy rain possible": "Возможен дождь", "Light rain": "Небольшой дождь",
    "Moderate rain": "Дождь", "Heavy rain": "Сильный дождь",
    "Light snow": "Небольшой снег", "Moderate snow": "Снег", "Heavy snow": "Сильный снег",
}

def get_real_weather(city_name: str = "Уфа") -> str:
    try:
        f_res = requests.get(f"https://wttr.in/{city_name}?format=j1", timeout=10)
        f_res.raise_for_status()
        f_data = f_res.json()
        current = f_data['current_condition'][0]
        temp = current['temp_C']
        desc_en = current['weatherDesc'][0]['value'].strip()
        desc_ru = WEATHER_TRANSLATION.get(desc_en, desc_en)
        return f"{temp}°C, {desc_ru.lower()}"
    except Exception:
        return "Данные о погоде недоступны"

def get_news_ufa() -> str:
    try:
        res = requests.get("https://news.mail.ru/rss/ufa/", timeout=5)
        res.encoding = 'utf-8'
        match = re.search(r'<item>.*?<title>(.*?)</title>', res.text, re.DOTALL)
        if match:
            news_title = match.group(1).strip()
            news_title = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', news_title)
            news_title = re.sub(r'<[^>]+>', '', news_title)
            return news_title
    except Exception:
        pass
    return "В Уфе всё спокойно."

def get_currency() -> str:
    try:
        res = requests.get("https://www.cbr-xml-daily.ru/daily_json.js", timeout=5).json()
        usd = res['Valute']['USD']['Value']
        eur = res['Valute']['EUR']['Value']
        return f"Доллар: {usd:.2f}, Евро: {eur:.2f}"
    except Exception:
        return "Курсы валют скрыты."

def get_traffic() -> str:
    return f"{random.randint(4, 8)} баллов из 10"

def dist_m(lat1, lon1, lat2, lon2):
    p1, p2 = radians(lat1), radians(lat2)
    a = sin((p2-p1)/2)**2 + cos(p1)*cos(p2)*sin(radians(lon2-lon1)/2)**2
    return 12742000 * asin(sqrt(a))

MAP_POIS = [
    {"name": "Гостиница Башкирия", "lat": 54.7269, "lon": 55.9438, "type": "hotel", "emoji": "🏨"},
    {"name": "Sheraton Plaza Ufa", "lat": 54.7214, "lon": 55.9421, "type": "hotel", "emoji": "🏨"},
    {"name": "Hampton by Hilton", "lat": 54.7295, "lon": 55.9465, "type": "hotel", "emoji": "🏨"},
    {"name": "AZIMUT Сити Отель", "lat": 54.7431, "lon": 55.9721, "type": "hotel", "emoji": "🏨"},
    {"name": "Бутик-отель Пушкин", "lat": 54.7238, "lon": 55.9412, "type": "hotel", "emoji": "🏨"},
    {"name": "Азык-Тулек", "lat": 54.7285, "lon": 55.9478, "type": "food", "emoji": "🍽️"},
    {"name": "AIBAT HALLYAR", "lat": 54.7310, "lon": 55.9502, "type": "food", "emoji": "🍽️"},
    {"name": "Дом башкирской кухни", "lat": 54.7355, "lon": 55.9580, "type": "food", "emoji": "🍽️"},
    {"name": "Ресторан Кунак", "lat": 54.7180, "lon": 55.9350, "type": "food", "emoji": "🍽️"},
    {"name": "Ресторан Rossinsky", "lat": 54.7205, "lon": 55.9410, "type": "food", "emoji": "🍽️"},
    {"name": "Памятник Салавату Юлаеву", "lat": 54.7323, "lon": 55.9425, "type": "attraction", "emoji": "🏛️"},
    {"name": "Гостиный Двор", "lat": 54.7150, "lon": 55.9450, "type": "attraction", "emoji": "🏛️"},
    {"name": "Парк Кашкадан", "lat": 54.7722, "lon": 55.9483, "type": "attraction", "emoji": "🌳"},
    {"name": "Национальный музей РБ", "lat": 54.7205, "lon": 55.9438, "type": "attraction", "emoji": "🏛️"},
    {"name": "Монумент Дружбы", "lat": 54.7330, "lon": 55.9420, "type": "attraction", "emoji": "🏛️"},
]

PROMO_PLACES = {
    "promo_term": {
        "title": "🏞 Термы «Стерлитамак»",
        "short_text": "Термы в Стерлитамаке — это вообще топ для перезагрузки! Горячие источники, спа, красота. Ехать от Уфы около 1,5 – 2 часов.",
        "full_text": "Термальный комплекс «Стерлитамак» — это уникальное место, где можно отдохнуть круглый год. Здесь есть несколько бассейнов с термальной водой разной температуры, сауны, хаммам, spa-процедуры и зоны отдыха. Вода богата минералами, что благотворно влияет на организм. Если хочешь снять усталость после дороги — это идеальный вариант. Добраться можно на такси (около 1,5 часов) или на автобусе (дольше, но дешевле).",
        "image": "https://images.unsplash.com/photo-1540555700478-4be289fbecef?q=80&w=800&auto=format&fit=crop"
    },
    "promo_mayakovsky": {
        "title": "☕ Кафе «Маяковский»",
        "short_text": "О, «Маяковский» — отличное место! Тут подают легендарный кофе и очень атмосферно. Находится в самом центре.",
        "full_text": "Кафе «Маяковский» — это культовое место в Уфе. Здесь подают отличный кофе, десерты и завтраки. Интерьер оформлен в стиле советского конструктивизма, с фотографиями и цитатами Владимира Маяковского. Это идеальное место для того, чтобы сделать паузу, согреться и почувствовать дух города. Находится в историческом центре, рядом с Гостиным двором.",
        "image": "https://images.unsplash.com/photo-1554118811-1e0d58224f24?q=80&w=800&auto=format&fit=crop"
    },
    "promo_azimut": {
        "title": "🏨 Отель «Азимут»",
        "short_text": "«Азимут» — надежный вариант, прямо в центре города, рядом с набережной. Очень удобно для прогулок.",
        "full_text": "Отель «Азимут» — современный 4-звездочный отель, расположенный в самом сердце Уфы, рядом с парком и набережной реки Белой. К услугам гостей просторные номера, фитнес-центр, ресторан и конференц-залы. Из окон открывается отличный вид на город. Это отличный выбор для тех, кто ценит комфорт и хочет быть в центре событий.",
        "image": "https://images.unsplash.com/photo-1566073771259-6a8506099945?q=80&w=800&auto=format&fit=crop"
    },
    "promo_gostiny": {
        "title": "🏛 Гостиный Двор",
        "short_text": "Гостиный Двор — это сердце Уфы, памятник архитектуры. Обязательно стоит прогуляться там и сделать классные фото.",
        "full_text": "Гостиный двор — один из главных исторических памятников Уфы. Здание было построено в начале XIX века и служило торговыми рядами. Здесь проходили ярмарки и важные городские события. Сегодня Гостиный двор — это не только памятник архитектуры, но и культурный центр, где проходят выставки, концерты и фестивали. Внутри есть уютные дворики и галереи, где можно прогуляться и почувствовать атмосферу старой Уфы.",
        "image": "https://images.unsplash.com/photo-1513326738677-b964603b136d?q=80&w=800&auto=format&fit=crop"
    },
    "promo_aksakov": {
        "title": "🎭 Музей Аксакова",
        "short_text": "Если любишь историю, тебе точно в музей Аксакова. Красивое старинное здание, интересные экскурсии.",
        "full_text": "Мемориальный дом-музей С. Т. Аксакова — это уникальный историко-культурный объект Уфы. Здесь прошли детские годы известного русского писателя Сергея Тимофеевича Аксакова. В музее воссоздана обстановка того времени, представлены личные вещи, книги и документы семьи Аксаковых. Экскурсия рассказывает о жизни и творчестве писателя, а также о быте уфимского дворянства XIX века.",
        "image": "https://images.unsplash.com/photo-1566121318462-5138885fdc4d?q=80&w=800&auto=format&fit=crop"
    },
    "promo_pavlovka": {
        "title": "🌲 База «Павловка»",
        "short_text": "Павловка — это наша жемчужина! Природа, водохранилище, чистый воздух. Идеально, чтобы сбежать от суеты.",
        "full_text": "Павловское водохранилище — это одно из самых живописных мест Башкирии. Здесь можно отдохнуть от городской суеты, насладиться чистым воздухом, порыбачить или просто прогуляться по лесу. На берегу есть базы отдыха с уютными домиками и банями. Зимой здесь катаются на снегоходах, летом — на лодках. Это идеальное место для тех, кто хочет сбежать от города на пару дней.",
        "image": "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?q=80&w=800&auto=format&fit=crop"
    }
}

KNOWN_ADDRESSES = {
    "термы стерлитамак": (53.6303, 55.9503),
    "термы": (53.6303, 55.9503),
    "гостиный двор": (54.7150, 55.9450),
    "дом аксакова": (54.7110, 55.9587),
    "музей аксакова": (54.7110, 55.9587),
    "памятник салавату юлаеву": (54.7323, 55.9425),
    "театр оперы и балета": (54.7218, 55.9438),
    "национальный музей": (54.7205, 55.9438),
    "парк кашкадан": (54.7722, 55.9483),
    "лимонарий": (54.7669, 55.9678),
    "мечеть ляля тюльпан": (54.7767, 55.9722),
    "железнодорожный вокзал уфа": (54.7488, 55.9617),
    "аэропорт уфа": (54.5575, 55.8736),
    "павловка": (54.4333, 56.8833),
    "павловское водохранилище": (54.4333, 56.8833),
}

CITY_ZONES = {
    "ufa_center":   {"coords": (54.7267, 55.9500), "radius": 3000},
    "ufa":          {"coords": (54.7388, 55.9721), "radius": 25000},
    "sterlitamak":  {"coords": (53.6304, 55.9310), "radius": 15000},
    "pavlovka":     {"coords": (54.4333, 56.8833), "radius": 10000},
}

def current_zone(lat, lon):
    if dist_m(lat, lon, *CITY_ZONES["ufa_center"]["coords"]) <= CITY_ZONES["ufa_center"]["radius"]: return "ufa_center"
    if dist_m(lat, lon, *CITY_ZONES["ufa"]["coords"]) <= CITY_ZONES["ufa"]["radius"]: return "ufa"
    if dist_m(lat, lon, *CITY_ZONES["sterlitamak"]["coords"]) <= CITY_ZONES["sterlitamak"]["radius"]: return "sterlitamak"
    if dist_m(lat, lon, *CITY_ZONES["pavlovka"]["coords"]) <= CITY_ZONES["pavlovka"]["radius"]: return "pavlovka"
    return "bashkortostan"

def get_taxi_link(start_lat, start_lon, end_lat, end_lon, tariff="econom"):
    q = {
        "start-lat": start_lat, "start-lon": start_lon,
        "end-lat": end_lat, "end-lon": end_lon,
        "tariffClass": tariff, "ref": "uje",
        "appmetrica_tracking_id": "25395763362139037"
    }
    return "https://3.redirect.appmetrica.yandex.com/route?" + urllib.parse.urlencode(q)

def _normalize_for_match(text: str) -> str:
    text = text.lower()
    for suffix in [", республика башкортостан", ", башкортостан", ", уфа", ", стерлитамак", ", павловка"]:
        text = text.replace(suffix, "")
    return text.strip()

def _find_known_address(query: str):
    normalized = _normalize_for_match(query)
    for key, coords in KNOWN_ADDRESSES.items():
        if key in normalized: return coords
    return None

def geocode_address(address: str, city: str = "Уфа"):
    known = _find_known_address(address)
    if known: return known
    try:
        url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(address + ', ' + city)}&format=json&limit=1"
        res = requests.get(url, headers={'User-Agent': 'BASHGID_Tourist_Guide/1.0'}, timeout=5).json()
        if res: return float(res[0]['lat']), float(res[0]['lon'])
    except Exception: pass
    return None, None