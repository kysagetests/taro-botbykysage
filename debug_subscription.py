import os
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


def debug_subscription(telegram_id):
    """Диагностика подписки пользователя"""
    print(f"🔍 ДИАГНОСТИКА ПОДПИСКИ ДЛЯ USER {telegram_id}")
    print("=" * 50)

    supabase_url = f"https://{os.getenv('SUPABASE_URL')}/rest/v1"
    headers = {
        'apikey': os.getenv('SUPABASE_KEY'),
        'Authorization': f"Bearer {os.getenv('SUPABASE_KEY')}",
    }

    # Получаем данные пользователя
    url = f"{supabase_url}/users?telegram_id=eq.{telegram_id}"
    response = requests.get(url, headers=headers)

    if response.status_code != 200 or not response.json():
        print("❌ Пользователь не найден")
        return

    user = response.json()[0]

    print("📊 ДАННЫЕ ИЗ БАЗЫ:")
    print(f"   • ID: {user.get('id')}")
    print(f"   • Имя: {user.get('first_name')}")
    print(f"   • Telegram ID: {user.get('telegram_id')}")
    print(f"   • subscription_type: {user.get('subscription_type')}")
    print(f"   • is_active: {user.get('is_active')}")
    print(f"   • subscription_start: {user.get('subscription_start')}")
    print(f"   • subscription_end: {user.get('subscription_end')}")
    print(f"   • predictions_count: {user.get('predictions_count')}")

    # Анализируем подписку
    subscription_end = user.get('subscription_end')
    subscription_type = user.get('subscription_type', 'free')
    is_active = user.get('is_active', True)

    print(f"\n🔍 АНАЛИЗ ПОДПИСКИ:")
    print(f"   • Тип подписки: {subscription_type}")
    print(f"   • Активен пользователь: {is_active}")

    has_subscription = False

    if subscription_end:
        try:
            # Обрабатываем дату
            if subscription_end.endswith('Z'):
                subscription_end_clean = subscription_end[:-1]
            else:
                subscription_end_clean = subscription_end

            sub_end_date = datetime.fromisoformat(subscription_end_clean)
            current_date = datetime.utcnow()

            print(f"\n📅 АНАЛИЗ ДАТ:")
            print(f"   • Текущее время UTC: {current_date}")
            print(f"   • Окончание подписки: {sub_end_date}")
            print(f"   • Разница: {sub_end_date - current_date}")
            print(f"   • Подписка не истекла: {sub_end_date > current_date}")

            # Проверяем все условия для активной подписки
            condition1 = subscription_type != 'free'
            condition2 = is_active
            condition3 = sub_end_date > current_date

            print(f"\n🎯 УСЛОВИЯ АКТИВНОЙ ПОДПИСКИ:")
            print(f"   • Подписка не free: {condition1} ({subscription_type})")
            print(f"   • Пользователь активен: {condition2} ({is_active})")
            print(f"   • Подписка не истекла: {condition3} ({sub_end_date} > {current_date})")

            has_subscription = condition1 and condition2 and condition3

        except Exception as e:
            print(f"❌ Ошибка парсинга даты: {e}")

    print(f"\n🎯 ИТОГОВЫЙ СТАТУС ПОДПИСКИ: {'✅ АКТИВНА' if has_subscription else '❌ НЕ АКТИВНА'}")

    # Проверяем возможность делать предсказания
    from config import FREE_PREDICTIONS_LIMIT
    predictions_count = user.get('predictions_count', 0)
    remaining = float('inf') if has_subscription else max(0, FREE_PREDICTIONS_LIMIT - predictions_count)

    print(f"\n🎯 ВОЗМОЖНОСТЬ ПРЕДСКАЗАНИЙ:")
    print(f"   • Сделано предсказаний: {predictions_count}")
    print(f"   • Лимит бесплатных: {FREE_PREDICTIONS_LIMIT}")
    print(f"   • Осталось предсказаний: {remaining}")
    print(f"   • Может делать предсказания: {'✅ ДА' if remaining > 0 else '❌ НЕТ'}")

    return user


def fix_subscription(telegram_id, days=30):
    """Исправить подписку пользователя"""
    print(f"\n🔧 ИСПРАВЛЕНИЕ ПОДПИСКИ ДЛЯ USER {telegram_id}")
    print("=" * 50)

    user = debug_subscription(telegram_id)
    if not user:
        return False

    supabase_url = f"https://{os.getenv('SUPABASE_URL')}/rest/v1"
    headers = {
        'apikey': os.getenv('SUPABASE_KEY'),
        'Authorization': f"Bearer {os.getenv('SUPABASE_KEY')}",
        'Content-Type': 'application/json',
        'Prefer': 'return=representation'
    }

    user_id = user['id']

    # Устанавливаем правильные даты
    subscription_start = datetime.utcnow() - timedelta(days=1)  # началась вчера
    subscription_end = datetime.utcnow() + timedelta(days=days)  # закончится через days дней

    update_data = {
        'subscription_type': 'premium',
        'subscription_start': subscription_start.isoformat() + 'Z',
        'subscription_end': subscription_end.isoformat() + 'Z',
        'is_active': True,
        'updated_at': datetime.utcnow().isoformat() + 'Z'
    }

    url = f"{supabase_url}/users?id=eq.{user_id}"
    response = requests.patch(url, headers=headers, json=update_data)

    if response.status_code == 200:
        print(f"✅ Подписка исправлена!")
        print(f"   • Начало: {subscription_start.strftime('%d.%m.%Y %H:%M')}")
        print(f"   • Окончание: {subscription_end.strftime('%d.%m.%Y %H:%M')}")
        print(f"   • Дней: {days}")

        # Проверяем исправление
        print(f"\n🔍 ПРОВЕРКА ИСПРАВЛЕНИЯ:")
        debug_subscription(telegram_id)
        return True
    else:
        print(f"❌ Ошибка исправления: {response.status_code} - {response.text}")
        return False


if __name__ == "__main__":
    # Замените на ваш Telegram ID
    TARGET_USER_ID = 6923428079

    print("🎯 ДИАГНОСТИКА И ИСПРАВЛЕНИЕ ПОДПИСКИ")
    print("=" * 60)

    # 1. Диагностика
    user_data = debug_subscription(TARGET_USER_ID)

    # 2. Предлагаем исправить
    if user_data:
        response = input("\n🧹 Исправить подписку? (y/N): ")
        if response.lower() == 'y':
            try:
                days = int(input("Количество дней подписки (30): ") or "30")
                fix_subscription(TARGET_USER_ID, days)
            except ValueError:
                print("❌ Неверное количество дней")