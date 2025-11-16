import os
import requests
from dotenv import load_dotenv

load_dotenv()


def clear_all_tickets():
    """Очистить все тикеты"""
    supabase_url = f"https://{os.getenv('SUPABASE_URL')}/rest/v1"
    headers = {
        'apikey': os.getenv('SUPABASE_KEY'),
        'Authorization': f"Bearer {os.getenv('SUPABASE_KEY')}",
    }

    # Сначала удаляем сообщения
    url = f"{supabase_url}/support_messages"
    response = requests.delete(url, headers=headers)
    print(f"🗑️ Удалено сообщений: {response.status_code}")

    # Затем удаляем тикеты
    url = f"{supabase_url}/support_tickets"
    response = requests.delete(url, headers=headers)
    print(f"🗑️ Удалено тикетов: {response.status_code}")


if __name__ == "__main__":
    clear_all_tickets()