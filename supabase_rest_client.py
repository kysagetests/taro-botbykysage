import os
from database_manager import DatabaseManager
from dotenv import load_dotenv

load_dotenv()


def test_rest_api_database():
    print("🧪 ТЕСТИРОВАНИЕ REST API DATABASE_MANAGER")
    print("=" * 50)

    db = DatabaseManager()

    # Тестовый пользователь
    class TestUser:
        def __init__(self):
            self.id = 777888999
            self.username = "test_rest_user"
            self.first_name = "REST"
            self.last_name = "Test"
            self.language_code = "ru"

    test_user = TestUser()

    # 1. Создаем/получаем пользователя
    print("1. Создание/получение пользователя...")
    user = db.get_or_create_user(test_user)
    if user:
        print(f"   ✅ Пользователь: {user['first_name']} (ID: {user['id']})")
        print(f"   📊 Предсказаний: {user['predictions_count']}")
    else:
        print("   ❌ Не удалось создать пользователя")
        return

    # 2. Тестируем предсказание
    print("2. Тестируем сохранение предсказания...")
    success = db.save_prediction(
        telegram_id=test_user.id,
        prediction_type="personal",
        user_name="Тест REST",
        partner_name="",
        birth_date="15.03.1990",
        zodiac_sign="Рыбы",
        cards=["Маг", "Императрица", "Шут"],
        prediction="Тестовое предсказание через REST API"
    )

    if success:
        print("   ✅ Предсказание сохранено")
    else:
        print("   ❌ Не удалось сохранить предсказание")

    # 3. Тестируем статистику
    print("3. Тестируем статистику...")
    stats = db.get_user_stats(test_user.id)
    if stats:
        print(f"   📊 Статистика: {stats['predictions_count']} предсказаний")
        print(f"   🎯 Осталось: {stats['remaining_predictions']}")
        print(f"   💎 Подписка: {stats['has_subscription']}")
    else:
        print("   ❌ Не удалось получить статистику")

    # 4. Тестируем историю
    print("4. Тестируем историю предсказаний...")
    history = db.get_user_predictions(test_user.id)
    print(f"   📚 Найдено предсказаний: {len(history)}")
    for pred in history:
        print(f"      • {pred['prediction_type']}: {', '.join(pred['cards_drawn'])}")

    # 5. Тестируем подписку
    print("5. Тестируем активацию подписки...")
    subscription_success = db.activate_subscription(test_user.id, 'premium', 30)
    if subscription_success:
        print("   ✅ Подписка активирована")

        # Проверяем статистику после подписки
        stats_after = db.get_user_stats(test_user.id)
        if stats_after and stats_after['has_subscription']:
            print("   💎 Подписка активна в статистике")
    else:
        print("   ❌ Не удалось активировать подписку")

    print("\n🎉 ТЕСТИРОВАНИЕ ЗАВЕРШЕНО!")


if __name__ == "__main__":
    test_rest_api_database()