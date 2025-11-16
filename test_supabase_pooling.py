import os
import socket
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()


def test_pooling_connection():
    print("🧪 ТЕСТИРОВАНИЕ ПОДКЛЮЧЕНИЯ ЧЕРЕЗ POOLING (6543)")
    print("=" * 50)

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_password = os.getenv("SUPABASE_PASSWORD")

    # Тестируем порт 6543
    print(f"1. Тестирование порта 6543...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    result = sock.connect_ex((supabase_url, 6543))
    sock.close()

    if result == 0:
        print("   ✅ Порт 6543 доступен!")
    else:
        print(f"   ❌ Порт 6543 недоступен (код ошибки: {result})")
        return False

    # Пробуем подключиться к базе
    print("2. Подключение к базе через pooling...")
    connection_url = f"postgresql+psycopg2://postgres:{supabase_password}@{supabase_url}:6543/postgres?sslmode=require"

    try:
        engine = create_engine(connection_url, connect_args={'connect_timeout': 10})

        with engine.connect() as conn:
            result = conn.execute(text("SELECT version(), NOW()"))
            row = result.fetchone()
            print(f"   ✅ Успешное подключение!")
            print(f"   🗄️ База: {row[0].split(',')[0]}")
            print(f"   🕐 Время: {row[1]}")
            return True

    except Exception as e:
        print(f"   ❌ Ошибка подключения: {e}")
        return False


if __name__ == "__main__":
    test_pooling_connection()