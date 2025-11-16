import os
from database_manager import DatabaseManager


def test_sqlite():
    print("🧪 Тестируем SQLite базу данных...")

    # Удаляем старую базу если есть
    if os.path.exists("tarot_bot.db"):
        os.remove("tarot_bot.db")
        print("🗑️ Удалена старая база данных")

    try:
        db = DatabaseManager()

        # Тестовый пользователь
        class TestUser:
            def __init__(self):
                self.id = 123456789
                self.username = "test_user_sqlite"
                self.first_name = "Test"
                self.last_name = "SQLite"
                self.language_code = "ru"

        test_user = TestUser()

        # Создаем/получаем пользователя
        user = db.get_or_create_user(test_user)
        if user:
            print(f"✅ Пользователь создан: {user['first_name']} (ID: {user['telegram_id']})")
            print(f"📊 Данные пользователя: {user}")
        else:
            print("❌ Не удалось создать пользователя")
            return

        # Проверяем статистику
        stats = db.get_user_stats(test_user.id)
        print(f"📊 Статистика: {stats}")

        # Тестируем предсказание
        success = db.save_prediction(
            telegram_id=user['telegram_id'],
            user_name="Тест SQLite",
            birth_date="15.03.1990",
            zodiac_sign="Рыбы",
            cards=["Маг", "Императрица", "Шут"],
            prediction="Тестовое предсказание в SQLite"
        )

        if success:
            print("✅ Предсказание сохранено")
        else:
            print("❌ Не удалось сохранить предсказание")

        # Проверяем историю
        history = db.get_user_predictions(user['telegram_id'])
        print(f"📚 История: {len(history)} записей")
        for pred in history:
            print(f"   - {pred['created_at']}: {pred['cards_drawn']}")

        # Тестируем подписку
        subscription_success = db.activate_subscription(user['telegram_id'], 'trial', 3)
        if subscription_success:
            print("✅ Подписка активирована")

        # Проверяем лимиты
        can_predict = db.can_user_make_prediction(user['telegram_id'])
        print(f"🎯 Может сделать предсказание: {can_predict}")

        # Проверяем статистику после подписки
        stats_after = db.get_user_stats(user['telegram_id'])
        print(f"📊 Статистика после подписки: {stats_after}")

        print("🎉 SQLite база работает отлично!")

    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_sqlite()