import logging
from main import TarotBot
from config import TELEGRAM_TOKEN, OPENROUTER_API_KEY, OPENROUTER_MODEL

logging.basicConfig(level=logging.INFO)


def main():
    if not TELEGRAM_TOKEN:
        print("❌ Установите TELEGRAM_TOKEN в .env файл")
        return

    print("🔮 Запуск бота-таролога...")
    print("📊 База данных: SQLite")
    print("🤖 Нейросеть: OpenRouter")
    print("🎯 Бесплатных предсказаний: 2")

    try:
        bot = TarotBot(TELEGRAM_TOKEN, OPENROUTER_API_KEY, OPENROUTER_MODEL)
        print("✅ Бот запущен!")
        print("🚀 Ожидаю сообщения...")
        bot.application.run_polling()

    except Exception as e:
        print(f"❌ Ошибка запуска бота: {e}")


if __name__ == "__main__":
    main()