import requests

def get_weather(city: str = "Уфа") -> str:
    """Получает текущую погоду в указанном городе БЕЗ API-ключей."""
    try:
        # Используем бесплатный сервис wttr.in (формат 3 = краткий текст)
        url = f"https://wttr.in/{city}?format=3&lang=ru"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return f"На улице: {response.text}"
        else:
            return "Не удалось узнать погоду, сервис временно недоступен."
    except Exception as e:
        return f"Ошибка при запросе погоды: {e}"