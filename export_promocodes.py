import os
import requests
from dotenv import load_dotenv
import logging
from datetime import datetime

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class PromoCodeExporter:
    def __init__(self):
        load_dotenv()
        self.supabase_url = f"https://{os.getenv('SUPABASE_URL')}/rest/v1"
        self.headers = {
            'apikey': os.getenv('SUPABASE_KEY'),
            'Authorization': f"Bearer {os.getenv('SUPABASE_KEY')}",
        }

    def get_all_promo_codes(self):
        """Получить все промокоды из базы"""
        try:
            url = f"{self.supabase_url}/promo_codes"
            params = {
                'select': 'code,days,max_uses,used_count,is_active,created_at',
                'order': 'created_at.desc'
            }

            response = requests.get(url, headers=self.headers, params=params)

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"❌ Ошибка получения промокодов: {response.status_code} - {response.text}")
                return []

        except Exception as e:
            logger.error(f"❌ Ошибка подключения к базе: {e}")
            return []

    def export_clean_list(self, filename=None):
        """Экспортировать чистый список кодов (только активные)"""
        promos = self.get_all_promo_codes()

        if not promos:
            logger.error("❌ Промокоды не найдены или ошибка подключения")
            return False

        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"promocodes_clean_{timestamp}.txt"

        try:
            with open(filename, 'w', encoding='utf-8') as f:
                # Только активные промокоды
                active_promos = [p for p in promos if p.get('is_active', True)]

                # Просто список кодов, каждый с новой строки
                for promo in active_promos:
                    f.write(f"{promo['code']}\n")

            logger.info(f"✅ Экспортировано {len(active_promos)} промокодов в: {filename}")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка записи в файл: {e}")
            return False

    def export_with_status(self, filename=None):
        """Экспортировать коды с пометкой статуса"""
        promos = self.get_all_promo_codes()

        if not promos:
            logger.error("❌ Промокоды не найдены")
            return False

        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"promocodes_status_{timestamp}.txt"

        try:
            with open(filename, 'w', encoding='utf-8') as f:
                active_promos = [p for p in promos if p.get('is_active', True)]

                f.write(f"Активных промокодов: {len(active_promos)}\n")
                f.write("=" * 20 + "\n\n")

                for promo in active_promos:
                    status = "✅" if promo.get('used_count', 0) < promo.get('max_uses', 1) else "❌"
                    f.write(f"{promo['code']} {status}\n")

            logger.info(f"✅ Экспортировано {len(active_promos)} промокодов в: {filename}")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка записи: {e}")
            return False


def main():
    """Основная функция"""
    print("🔮 Экспорт промокодов из базы данных")
    print("=" * 40)

    exporter = PromoCodeExporter()

    while True:
        print("\nВыберите действие:")
        print("1. 📄 Чистый список (только коды)")
        print("2. 📊 Список со статусами")
        print("3. 🚪 Выход")

        choice = input("\nВаш выбор (1-3): ").strip()

        if choice == '1':
            filename = input("Имя файла (или Enter для автоимени): ").strip()
            if not filename:
                filename = None
            exporter.export_clean_list(filename)

        elif choice == '2':
            filename = input("Имя файла (или Enter для автоимени): ").strip()
            if not filename:
                filename = None
            exporter.export_with_status(filename)

        elif choice == '3':
            print("👋 До свидания!")
            break

        else:
            print("❌ Неверный выбор, попробуйте снова")


if __name__ == "__main__":
    main()