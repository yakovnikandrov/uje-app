import asyncio
from ai_brain import ask_uje

async def main():
    print("⏳ Отправляю тестовый запрос в YandexGPT...")
    try:
        # Ждем ответ максимум 10 секунд
        response = await asyncio.wait_for(ask_uje("Привет! Напиши слово 'Работает'"), timeout=10.0)
        print(f"\n✅ УСПЕХ! Ответ от ИИ:\n{response}")
    except asyncio.TimeoutError:
        print("\n❌ ОШИБКА: Таймаут. Яндекс не ответил за 10 секунд.")
        print("Проверь: 1) Баланс в Яндекс.Облаке (должен быть > 0) 2) Выключен ли VPN")
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")

if __name__ == "__main__":
    asyncio.run(main())