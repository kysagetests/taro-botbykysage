import random
import string
from datetime import datetime, timedelta
from database_manager import DatabaseManager
import logging

logger = logging.getLogger(__name__)


class PromoCodeManager:
    def __init__(self, database: DatabaseManager):
        self.db = database

    def generate_random_code(self, length: int = 8, prefix: str = "TAROT") -> str:
        """Генерация случайного промокода"""
        chars = string.ascii_uppercase + string.digits
        random_part = ''.join(random.choice(chars) for _ in range(length))
        return f"{prefix}{random_part}"

    def create_promo_batch(self, count: int, days: int, max_uses: int = 1,
                           created_by: int = None, prefix: str = "TAROT") -> list:
        """Создание партии промокодов"""
        created_codes = []

        for i in range(count):
            code = self.generate_random_code(prefix=prefix)
            success = self.db.create_promo_code(
                code=code,
                days=days,
                max_uses=max_uses,
                created_by=created_by,
                description=f"Автогенерированный код #{i + 1}"
            )

            if success:
                created_codes.append(code)
                logger.info(f"✅ Успешно создан промокод: {code}")
            else:
                logger.error(f"❌ Не удалось создать код: {code}")

        logger.info(f"📊 Создано {len(created_codes)} из {count} промокодов")
        return created_codes

    def create_custom_promo(self, code: str, days: int, max_uses: int = 1,
                            created_by: int = None, description: str = "") -> bool:
        """Создание кастомного промокода"""
        return self.db.create_promo_code(
            code=code,
            days=days,
            max_uses=max_uses,
            created_by=created_by,
            description=description
        )

    def get_promo_stats(self) -> dict:
        """Статистика по промокодам"""
        try:
            promos = self.db.get_all_promo_codes()

            if not promos:
                return {
                    'total_codes': 0,
                    'active_codes': 0,
                    'used_codes': 0,
                    'total_uses': 0
                }

            total = len(promos)
            active = sum(1 for p in promos if p.get('is_active', False))
            used = sum(1 for p in promos if p.get('used_count', 0) > 0)
            total_uses = sum(p.get('used_count', 0) for p in promos)

            return {
                'total_codes': total,
                'active_codes': active,
                'used_codes': used,
                'total_uses': total_uses
            }
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики промокодов: {e}")
            return {
                'total_codes': 0,
                'active_codes': 0,
                'used_codes': 0,
                'total_uses': 0
            }


# Пример использования
if __name__ == "__main__":
    db = DatabaseManager()
    promo_manager = PromoCodeManager(db)

    # Создание 10 промокодов на 30 дней
    codes = promo_manager.create_promo_batch(10, 30, created_by=1)
    print(f"Созданы коды: {codes}")

    # Создание кастомного кода
    promo_manager.create_custom_promo("SUMMER2024", 60, 5, 1, "Летняя акция")

    # Статистика
    stats = promo_manager.get_promo_stats()
    print(f"Статистика: {stats}")