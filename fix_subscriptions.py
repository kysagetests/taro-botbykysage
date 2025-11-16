import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()


def fix_all_subscriptions():
    """Исправляет все подписки в базе"""
    print("🔧 ИСПРАВЛЕНИЕ ВСЕХ ПОДПИСОК")
    print("=" * 40)

    supabase_url = f"https://{os.getenv('SUPABASE_URL')}/rest/v1"
    headers = {
        'apikey': os.getenv('SUPABASE_KEY'),
        'Authorization': f"Bearer {os.getenv('SUPABASE_KEY')}",
        'Content-Type': 'application/json',
        'Prefer': 'return=representation'
    }

    # Получаем всех пользователей с подписками
    url = f"{supabase_url}/users?subscription_type=neq.free&select=id,telegram_id,first_name,subscription_type,subscription_end"
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print("❌ Ошибка получения пользователей")
        return

    users = response.json()
    print(f"📊 Найдено пользователей с подписками: {len(users)}")

    fixed_count = 0
    for user in users:
        user_id = user['id']
        telegram_id = user['telegram_id']

        # Проверяем текущую подписку
        subscription_end = user.get('subscription_end')
        needs_fix = False

        if subscription_end:
            try:
                if subscription_end.endswith('Z'):
                    subscription_end = subscription_end[:-1]
                sub_end_date = datetime.fromisoformat(subscription_end)
                if sub_end_date <= datetime.utcnow():
                    needs_fix = True
            except:
                needs_fix = True
        else:
            needs_fix = True

        if needs_fix:
            # Исправляем подписку
            subscription_end = datetime.utcnow() + timedelta(days=30)

            update_data = {
                'subscription_start': datetime.utcnow().isoformat() + 'Z',
                'subscription_end': subscription_end.isoformat() + 'Z',
                'is_active': True,
                'updated_at': datetime.utcnow().isoformat() + 'Z'
            }

            update_url = f"{supabase_url}/users?id=eq.{user_id}"
            response = requests.patch(update_url, headers=headers, json=update_data)

            if response.status_code == 200:
                print(f"✅ Исправлена подписка для {user['first_name']} ({telegram_id})")
                fixed_count += 1
            else:
                print(f"❌ Ошибка для {user['first_name']}: {response.status_code}")

    print(f"\n🎯 ИТОГО: исправлено {fixed_count} из {len(users)} подписок")


def grant_subscription_to_user(telegram_id, days=30):
    """Выдать подписку конкретному пользователю"""
    print(f"🎁 ВЫДАЧА ПОДПИСКИ ПОЛЬЗОВАТЕЛЮ {telegram_id}")
    print("=" * 40)

    supabase_url = f"https://{os.getenv('SUPABASE_URL')}/rest/v1"
    headers = {
        'apikey': os.getenv('SUPABASE_KEY'),
        'Authorization': f"Bearer {os.getenv('SUPABASE_KEY')}",
        'Content-Type': 'application/json',
        'Prefer': 'return=representation'
    }

    # Находим пользователя
    url = f"{supabase_url}/users?telegram_id=eq.{telegram_id}"
    response = requests.get(url, headers=headers)

    if response.status_code != 200 or not response.json():
        print(f"❌ Пользователь {telegram_id} не найден")
        return False

    user = response.json()[0]
    user_id = user['id']

    # Устанавливаем подписку
    subscription_start = datetime.utcnow()
    subscription_end = subscription_start + timedelta(days=days)

    update_data = {
        'subscription_type': 'premium',
        'subscription_start': subscription_start.isoformat() + 'Z',
        'subscription_end': subscription_end.isoformat() + 'Z',
        'is_active': True,
        'updated_at': datetime.utcnow().isoformat() + 'Z'
    }

    update_url = f"{supabase_url}/users?id=eq.{user_id}"
    response = requests.patch(update_url, headers=headers, json=update_data)

    if response.status_code == 200:
        print(f"✅ Подписка выдана пользователю {user['first_name']}")
        print(f"   • Действует с: {subscription_start.strftime('%d.%m.%Y %H:%M')}")
        print(f"   • Действует до: {subscription_end.strftime('%d.%m.%Y %H:%M')}")
        print(f"   • Дней: {days}")
        return True
    else:
        print(f"❌ Ошибка выдачи подписки: {response.status_code}")
        return False


if __name__ == "__main__":
    print("🎯 ИНСТРУМЕНТЫ ДЛЯ РАБОТЫ С ПОДПИСКАМИ")
    print("=" * 50)

    print("1. Исправить все подписки в базе")
    print("2. Выдать подписку конкретному пользователю")
    print("3. Выход")

    choice = input("Выберите действие: ").strip()

    if choice == '1':
        fix_all_subscriptions()
    elif choice == '2':
        try:
            telegram_id = int(input("Введите Telegram ID: "))
            days = int(input("Количество дней (30): ") or "30")
            grant_subscription_to_user(telegram_id, days)
        except ValueError:
            print("❌ Неверный формат ID или количества дней")
    elif choice == '3':
        print("👋 Выход")
    else:
        print("❌ Неверный выбор")