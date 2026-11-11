# tools.py
import requests
import urllib.parse
import re
import random

def check_bus(stop): return "🚌 Автобус приедет через 5 минут."
def play_music(genre): return f"Включаю {genre}."
def order_food(dish): return f"Заказываю {dish}."

WEATHER_TRANSLATION = {
    "Sunny": "Солнечно", "Clear": "Ясно", "Partly cloudy": "Переменная облачность",
    "Cloudy": "Облачно", "Overcast": "Пасмурно", "Mist": "Туман", "Fog": "Туман",
    "Patchy rain possible": "Возможен дождь", "Patchy rain nearby": "Местами дождь",
    "Light rain": "Небольшой дождь", "Light rain shower": "Легкий дождь",
    "Moderate rain": "Дождь", "Moderate rain at times": "Временами дождь",
    "Heavy rain": "Сильный дождь", "Heavy rain at times": "Временами сильный дождь",
    "Light drizzle": "Морось", "Patchy light drizzle": "Местами морось",
    "Light snow": "Небольшой снег", "Light snow showers": "Небольшой снегопад",
    "Moderate snow": "Снег", "Heavy snow": "Сильный снег", "Blizzard": "Метель",
    "Patchy snow possible": "Возможен снег", "Patchy light snow": "Местами небольшой снег",
    "Patchy moderate snow": "Местами снег", "Patchy heavy snow": "Местами сильный снег",
    "Thundery outbreaks possible": "Возможна гроза", "Patchy light rain with thunder": "Местами дождь с грозой",
    "Moderate or heavy rain with thunder": "Гроза с дождем"
}

def get_real_weather(city_name: str = "Уфа") -> str:
    try:
        fallback_url = f"https://wttr.in/{city_name}?format=j1"
        f_res = requests.get(fallback_url, timeout=10)
        f_res.raise_for_status()
        f_data = f_res.json()
        
        current = f_data['current_condition'][0]
        temp = current['temp_C']
        desc_en = current['weatherDesc'][0]['value'].strip()
        
        # Ищем перевод, если не нашли - оставляем как есть (но обычно все покрыто)
        desc_ru = WEATHER_TRANSLATION.get(desc_en, desc_en)
        
        return f"{temp}°C, {desc_ru.lower()}"
    except Exception as e:
        print(f"⚠️ Ошибка погоды: {e}")
        return "Данные о погоде недоступны"

def get_news_ufa() -> str:
    try:
        url = "https://news.mail.ru/rss/ufa/"
        res = requests.get(url, timeout=5)
        res.encoding = 'utf-8'
        match = re.search(r'<item>.*?<title>(.*?)</title>', res.text, re.DOTALL)
        if match:
            news_title = match.group(1).strip()
            news_title = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', news_title)
            news_title = re.sub(r'<[^>]+>', '', news_title)
            return news_title
    except Exception as e:
        print(f"⚠️ Ошибка новостей: {e}")
    return "В Уфе всё спокойно, никаких громких заголовков."

def get_currency() -> str:
    try:
        res = requests.get("https://www.cbr-xml-daily.ru/daily_json.js", timeout=5).json()
        usd = res['Valute']['USD']['Value']
        eur = res['Valute']['EUR']['Value']
        return f"Доллар: {usd:.2f}, Евро: {eur:.2f}"
    except Exception as e:
        print(f"⚠️ Ошибка валют: {e}")
        return "Курсы валют скрыты от нас"

def get_traffic() -> str:
    score = random.randint(4, 8)
    return f"{score} баллов из 10"

def get_taxi_link(pickup_lat: float, pickup_lon: float, dest_address: str) -> str:
    dest_encoded = urllib.parse.quote(dest_address)
    return f"https://yandex.ru/maps/?rtext={pickup_lat},{pickup_lon}~{dest_encoded}&rtt=auto"