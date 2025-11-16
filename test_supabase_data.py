import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
import logging
from datetime import datetime, timedelta
import json
import random
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_environment_variables():
    """Проверяет наличие всех необходимых переменных окружения"""
    print("🔍 ПРОВЕРКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ")
    print("=" * 40)

    required_vars = {
        'SUPABASE_URL': os.getenv("SUPABASE_URL"),
        'SUPABASE_PASSWORD': os.getenv("SUPABASE_PASSWORD"),
        'SUPABASE_KEY': os.getenv("SUPABASE_KEY"),
        'TELEGRAM_TOKEN': os.getenv("TELEGRAM_TOKEN")
    }

    all_ok = True
    for var_name, var_value in required_vars.items():
        status = "✅" if var_value else "❌"
        display_value = var_value if var_value else "НЕ УСТАНОВЛЕНА"
        if var_name == "SUPABASE_PASSWORD" and var_value:
            display_value = "*" * len(var_value)
        print(f"   {status} {var_name}: {display_value}")

        if not var_value:
            all_ok = False

    return all_ok


def get_connection():
    """Создает подключение к Supabase"""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_password = os.getenv("SUPABASE_PASSWORD")

    if not supabase_url or not supabase_password:
        print("❌ Отсутствуют переменные окружения SUPABASE_URL или SUPABASE_PASSWORD")
        return None

    # Пробуем разные варианты подключения
    connection_urls = [
        f"postgresql+psycopg2://postgres:{supabase_password}@{supabase_url}:5432/postgres",
        f"postgresql+psycopg2://postgres:{supabase_password}@{supabase_url}:5432/postgres?sslmode=require",
        f"postgresql+psycopg2://postgres:{supabase_password}@{supabase_url}:5432/postgres?sslmode=disable",
    ]

    for connection_url in connection_urls:
        try:
            print(f"🔄 Пробую подключиться: {connection_url.split('@')[1].split('/')[0]}")

            engine = create_engine(
                connection_url,
                pool_pre_ping=True,
                connect_args={'connect_timeout': 10}
            )

            # Тестируем подключение
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            print(f"✅ Успешное подключение!")
            return engine

        except OperationalError as e:
            print(f"   ❌ Ошибка: {e}")
            continue
        except Exception as e:
            print(f"   ❌ Неожиданная ошибка: {e}")
            continue

    print("❌ Все попытки подключения провалились")
    return None


def test_connection():
    """Тестирует подключение к базе"""
    print("\n🔌 ТЕСТ ПОДКЛЮЧЕНИЯ К SUPABASE")
    print("=" * 40)

    engine = get_connection()
    if not engine:
        return False

    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version(), NOW() as server_time, current_database()"))
            row = result.fetchone()
            print(f"✅ Подключение успешно!")
            print(f"   🗄️ База данных: {row[2]}")
            print(f"   🕐 Время сервера: {row[1]}")
            print(f"   🔧 PostgreSQL: {row[0].split(',')[0]}")
            return True
    except Exception as e:
        print(f"❌ Ошибка при тестировании подключения: {e}")
        return False


def list_tables():
    """Показывает список таблиц"""
    print("\n📊 СУЩЕСТВУЮЩИЕ ТАБЛИЦЫ")
    print("=" * 40)

    engine = get_connection()
    if not engine:
        return

    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                ORDER BY table_name
            """))
            tables = result.fetchall()

            if tables:
                print("📋 Найдены таблицы:")
                for table in tables:
                    print(f"   • {table[0]}")
            else:
                print("ℹ️ Таблицы не найдены")

    except Exception as e:
        print(f"❌ Ошибка при получении списка таблиц: {e}")


def test_simple_operations():
    """Простой тест операций с данными"""
    print("\n🧪 ПРОСТОЙ ТЕСТ ОПЕРАЦИЙ С ДАННЫМИ")
    print("=" * 40)

    engine = get_connection()
    if not engine:
        return

    try:
        with engine.connect() as conn:
            # 1. Проверяем существование таблицы users
            print("1. Проверка таблицы users...")
            try:
                result = conn.execute(text("SELECT COUNT(*) FROM users"))
                user_count = result.fetchone()[0]
                print(f"   ✅ Таблица users существует, записей: {user_count}")
            except:
                print("   ❌ Таблица users не существует или недоступна")
                return

            # 2. Создаем тестового пользователя
            print("2. Создание тестового пользователя...")
            test_telegram_id = random.randint(100000000, 999999999)

            insert_sql = """
            INSERT INTO users (telegram_id, username, first_name, last_name, language_code)
            VALUES (:telegram_id, :username, :first_name, :last_name, :language_code)
            RETURNING id, telegram_id, first_name
            """

            result = conn.execute(text(insert_sql), {
                'telegram_id': test_telegram_id,
                'username': 'test_user_supabase',
                'first_name': 'Тест',
                'last_name': 'Супабейс',
                'language_code': 'ru'
            })

            new_user = result.fetchone()
            conn.commit()
            print(f"   ✅ Создан пользователь: {new_user[2]} (ID: {new_user[0]})")

            # 3. Проверяем чтение пользователя
            print("3. Чтение пользователя...")
            select_sql = "SELECT first_name, username FROM users WHERE id = :user_id"
            result = conn.execute(text(select_sql), {'user_id': new_user[0]})
            user = result.fetchone()

            if user:
                print(f"   ✅ Прочитан пользователь: {user[0]} (@{user[1]})")

            # 4. Обновляем пользователя
            print("4. Обновление пользователя...")
            update_sql = """
            UPDATE users 
            SET predictions_count = 5,
                updated_at = NOW()
            WHERE id = :user_id
            RETURNING predictions_count
            """

            result = conn.execute(text(update_sql), {'user_id': new_user[0]})
            new_count = result.fetchone()[0]
            conn.commit()
            print(f"   ✅ Обновлен счетчик предсказаний: {new_count}")

            # 5. Удаляем тестового пользователя
            print("5. Очистка тестовых данных...")
            delete_sql = "DELETE FROM users WHERE id = :user_id"
            conn.execute(text(delete_sql), {'user_id': new_user[0]})
            conn.commit()
            print(f"   ✅ Тестовый пользователь удален")

            return True

    except Exception as e:
        print(f"❌ Ошибка при тестировании операций: {e}")
        return False


def show_database_info():
    """Показывает информацию о базе данных"""
    print("\n📈 ИНФОРМАЦИЯ О БАЗЕ ДАННЫХ")
    print("=" * 40)

    engine = get_connection()
    if not engine:
        return

    try:
        with engine.connect() as conn:
            # Информация о базе
            result = conn.execute(text("""
                SELECT 
                    current_database() as db_name,
                    current_user as db_user,
                    inet_server_addr() as server_ip,
                    inet_server_port() as server_port
            """))
            db_info = result.fetchone()

            print("🔧 Информация о подключении:")
            print(f"   • База данных: {db_info[0]}")
            print(f"   • Пользователь: {db_info[1]}")
            print(f"   • Сервер: {db_info[2]}:{db_info[3]}")

            # Размер базы данных
            result = conn.execute(text("""
                SELECT pg_size_pretty(pg_database_size(current_database())) as db_size
            """))
            db_size = result.fetchone()[0]
            print(f"   • Размер базы: {db_size}")

    except Exception as e:
        print(f"❌ Ошибка при получении информации о БД: {e}")


def test_network_connection():
    """Тестирует сетевое подключение"""
    print("\n🌐 ТЕСТ СЕТЕВОГО ПОДКЛЮЧЕНИЯ")
    print("=" * 40)

    import socket
    import subprocess

    supabase_url = os.getenv("SUPABASE_URL")

    if not supabase_url:
        print("❌ SUPABASE_URL не установлена")
        return

    try:
        # Тестируем DNS разрешение
        print(f"1. DNS разрешение {supabase_url}...")
        ip_address = socket.gethostbyname(supabase_url)
        print(f"   ✅ IP адрес: {ip_address}")

        # Тестируем ping (только на Windows/Linux)
        print("2. Тестирование ping...")
        try:
            param = "-n" if os.name == "nt" else "-c"
            result = subprocess.run(
                ["ping", param, "3", supabase_url],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                print("   ✅ Ping успешен")
            else:
                print("   ⚠️ Ping не удался (может быть заблокирован)")
        except:
            print("   ⚠️ Ping тест пропущен")

        # Тестируем подключение к порту 5432
        print("3. Тестирование порта 5432...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((supabase_url, 5432))
        sock.close()

        if result == 0:
            print("   ✅ Порт 5432 доступен")
        else:
            print(f"   ❌ Порт 5432 недоступен (код ошибки: {result})")

    except Exception as e:
        print(f"❌ Ошибка сетевого тестирования: {e}")


def main():
    """Основная функция тестирования"""
    print("🎯 ТЕСТИРОВАНИЕ ПОДКЛЮЧЕНИЯ К SUPABASE")
    print("=" * 50)

    # Проверяем переменные окружения
    if not check_environment_variables():
        print("\n❌ Не все переменные окружения установлены!")
        print("Убедитесь, что в файле .env есть:")
        print("SUPABASE_URL=mgrzsjptkwbkiqufcnjt.supabase.co")
        print("SUPABASE_PASSWORD=Odanus203_")
        print("SUPABASE_KEY=ваш_ключ")
        return

    # Тестируем сетевое подключение
    test_network_connection()

    # Тестируем подключение к базе
    if test_connection():
        # Показываем информацию о БД
        show_database_info()

        # Показываем таблицы
        list_tables()

        # Тестируем простые операции
        test_simple_operations()

        print("\n🎉 ТЕСТИРОВАНИЕ ЗАВЕРШЕНО УСПЕШНО!")
    else:
        print("\n💡 ВОЗМОЖНЫЕ РЕШЕНИЯ:")
        print("1. Проверьте настройки фаервола")
        print("2. Убедитесь, что в Supabase включен доступ со всех IP")
        print("3. Проверьте правильность пароля базы данных")
        print("4. Попробуйте использовать VPN")


if __name__ == "__main__":
    main()