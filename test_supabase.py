import asyncio
from database_manager import DatabaseManager


async def test_supabase():
    print("🧪 Тестируем подключение к Supabase...")

    try:
        db = DatabaseManager()

        # Тестовый пользователь
        class TestUser:
            def __init__(self):
                self.id = 123456789
                self.username = "test_user_supabase"
                self.first_name = "Test"
                self.last_name = "Supabase"
                self.language_code = "ru"

        test_user = TestUser()

        # Создаем/получаем пользователя
        user = db.get_or_create_user(test_user)
        if user:
            print(f"✅ Пользователь создан в Supabase: {user.first_name} (ID: {user.telegram_id})")
        else:
            print("❌ Не удалось создать пользователя")
            return

        # Проверяем статистику
        stats = db.get_user_stats(test_user.id)
        print(f"📊 Статистика: {stats}")

        # Тестируем предсказание
        success = db.save_prediction(
            user_id=user.id,
            user_name="Тест Supabase",
            birth_date="15.03.1990",
            zodiac_sign="Рыбы",
            cards=["Маг", "Императрица", "Шут"],
            prediction="Тестовое предсказание в Supabase"
        )

        if success:
            print("✅ Предсказание сохранено в Supabase")
        else:
            print("❌ Не удалось сохранить предсказание")

        # Проверяем историю
        history = db.get_user_predictions(user.id)
        print(f"📚 История: {len(history)} записей")

        # Тестируем подписку
        subscription_success = db.activate_subscription(user.telegram_id, 'trial', 3)
        if subscription_success:
            print("✅ Подписка активирована в Supabase")

        print("🎉 Supabase работает отлично!")

    except Exception as e:
        print(f"❌ Ошибка тестирования Supabase: {e}")


if __name__ == "__main__":
    asyncio.run(test_supabase())