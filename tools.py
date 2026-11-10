import requests

def get_weather(city: str = "Уфа") -> str:
    try:
        url = f"https://wttr.in/{city}?format=3&lang=ru"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return f"На улице: {response.text}"
        return "Не удалось узнать погоду."
    except Exception as e:
        return f"Ошибка при запросе погоды: {e}"

def call_taxi(pickup: str, destination: str) -> str:
    # Здесь будет реальный API такси
    return f"🚕 Принято! Вызываю такси от '{pickup}' до '{destination}'. Машина будет через 4 минуты."

def check_bus(stop: str) -> str:
    # Здесь будет реальный API транспорта
    return f"🚌 Вижу тебя на остановке '{stop}'. Твой автобус будет через 4 минуты."

def play_music(genre: str) -> str:
    # Здесь будет интеграция с Audius
    return f"🎵 Включаю {genre}. Первый трек из топа уже играет!"

def order_food(dish: str) -> str:
    # Здесь будет интеграция с доставкой
    return f"🍣 Отлично! Я нашел '{dish}' в лучших доставках Уфы. Оформляю заказ!"