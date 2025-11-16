import os
import requests
import json
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from config import ADMIN_IDS

# Загружаем переменные окружения
load_dotenv()

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self):
        self.supabase_url = f"https://{os.getenv('SUPABASE_URL')}/rest/v1"
        self.headers = {
            'apikey': os.getenv('SUPABASE_KEY'),
            'Authorization': f"Bearer {os.getenv('SUPABASE_KEY')}",
            'Content-Type': 'application/json',
            'Prefer': 'return=representation'
        }

        # Кэш для пользователей
        self.users_cache = {}

        logger.info("✅ Supabase REST API клиент инициализирован")

    def _make_request(self, endpoint, method='GET', data=None, params=None):
        """Универсальный метод для выполнения запросов"""
        url = f"{self.supabase_url}/{endpoint}"

        try:
            if method == 'GET':
                response = requests.get(url, headers=self.headers, params=params, timeout=10)
            elif method == 'POST':
                response = requests.post(url, headers=self.headers, json=data, timeout=10)
            elif method == 'PATCH':
                response = requests.patch(url, headers=self.headers, json=data, timeout=10)
            elif method == 'DELETE':
                response = requests.delete(url, headers=self.headers, timeout=10)
            else:
                raise ValueError(f"Неизвестный метод: {method}")

            if response.status_code in [200, 201]:
                return response.json() if response.content else True
            else:
                logger.error(f"❌ HTTP {response.status_code}: {response.text}")
                return None

        except requests.exceptions.Timeout:
            logger.error(f"❌ Таймаут запроса к {endpoint}")
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка запроса к {endpoint}: {e}")
            return None

    def _parse_supabase_date(self, date_string):
        """Парсит дату из Supabase в datetime объект"""
        if not date_string:
            return None

        try:
            # Supabase возвращает даты в формате: "2025-11-12 23:01:44.064297+00"
            # Пробуем разные форматы
            formats = [
                '%Y-%m-%d %H:%M:%S.%f%z',  # С микросекундами и временной зоной
                '%Y-%m-%d %H:%M:%S%z',  # Без микросекунд с временной зоной
                '%Y-%m-%dT%H:%M:%S.%f%z',  # ISO с микросекундами
                '%Y-%m-%dT%H:%M:%S%z',  # ISO без микросекунд
                '%Y-%m-%d %H:%M:%S',  # Без временной зоны
                '%Y-%m-%dT%H:%M:%S',  # ISO без временной зоны
            ]

            for fmt in formats:
                try:
                    return datetime.strptime(date_string, fmt)
                except ValueError:
                    continue

            # Если ни один формат не подошел, пробуем убрать микросекунды
            if '.' in date_string and '+' in date_string:
                parts = date_string.split('.')
                if len(parts) == 2:
                    date_part = parts[0]
                    timezone_part = parts[1].split('+')[1] if '+' in parts[1] else parts[1].split('-')[1] if '-' in \
                                                                                                             parts[
                                                                                                                 1] else ''
                    clean_date = f"{date_part}+{timezone_part}"
                    return datetime.strptime(clean_date, '%Y-%m-%d %H:%M:%S%z')

            logger.error(f"❌ Не удалось распарсить дату: {date_string}")
            return None

        except Exception as e:
            logger.error(f"❌ Ошибка парсинга даты {date_string}: {e}")
            return None

    def _is_subscription_active(self, user_data):
        """Проверяет активна ли подписка пользователя"""
        subscription_end = user_data.get('subscription_end')
        subscription_type = user_data.get('subscription_type', 'free')
        is_active = user_data.get('is_active', True)

        logger.info(f"🔍 Проверка подписки: type={subscription_type}, active={is_active}, end={subscription_end}")

        # Если подписка free или не активна
        if subscription_type == 'free' or not is_active:
            logger.info("❌ Подписка free или пользователь не активен")
            return False

        # Если нет даты окончания
        if not subscription_end:
            logger.info("❌ Нет даты окончания подписки")
            return False

        try:
            # Парсим дату окончания подписки
            sub_end_date = self._parse_supabase_date(subscription_end)
            current_date = datetime.utcnow().replace(
                tzinfo=sub_end_date.tzinfo) if sub_end_date and sub_end_date.tzinfo else datetime.utcnow()

            if not sub_end_date:
                logger.error("❌ Не удалось распарсить дату окончания подписки")
                return False

            logger.info(f"🔍 Сравнение дат: сейчас {current_date}, окончание {sub_end_date}")
            logger.info(f"🔍 Подписка активна: {sub_end_date > current_date}")

            # Подписка активна если дата окончания в будущем
            return sub_end_date > current_date

        except Exception as e:
            logger.error(f"❌ Ошибка проверки подписки: {e}")
            return False

    def get_or_create_user(self, telegram_user):
        """Получить или создать пользователя"""
        # Проверяем кэш
        cache_key = str(telegram_user.id)
        if cache_key in self.users_cache:
            return self.users_cache[cache_key]

        # Ищем существующего пользователя
        users = self._make_request('users', params={'telegram_id': f'eq.{telegram_user.id}'})

        if users and len(users) > 0:
            user = users[0]
            logger.info(f"✅ Пользователь найден: {user['first_name']}")
            self.users_cache[cache_key] = user
            return user

        # Создаем нового пользователя
        user_data = {
            'telegram_id': telegram_user.id,
            'username': telegram_user.username or '',
            'first_name': telegram_user.first_name or '',
            'last_name': telegram_user.last_name or '',
            'language_code': telegram_user.language_code or 'ru',
            'predictions_count': 0,
            'total_spent': 0,
            'subscription_type': 'free',
            'is_active': True,
            'created_at': datetime.utcnow().isoformat() + 'Z'
        }

        new_user = self._make_request('users', method='POST', data=user_data)

        if new_user and len(new_user) > 0:
            user = new_user[0]
            logger.info(f"✅ Создан новый пользователь: {user['first_name']}")
            self.users_cache[cache_key] = user
            return user

        logger.error(f"❌ Не удалось создать пользователя для {telegram_user.id}")
        return None

    def get_user_stats(self, telegram_id: int):
        """Получить статистику пользователя"""
        try:
            user = self._make_request('users', params={'telegram_id': f'eq.{telegram_id}'})
            if not user or len(user) == 0:
                return None

            user_data = user[0]

            from config import FREE_PREDICTIONS_LIMIT

            # Проверяем активна ли подписка
            has_subscription = self._is_subscription_active(user_data)

            remaining_predictions = (
                float('inf') if has_subscription
                else max(0, FREE_PREDICTIONS_LIMIT - user_data['predictions_count'])
            )

            # Форматируем дату для красивого отображения
            subscription_end = user_data.get('subscription_end')
            subscription_end_formatted = "неизвестно"

            if subscription_end:
                try:
                    end_date = self._parse_supabase_date(subscription_end)
                    if end_date:
                        subscription_end_formatted = end_date.strftime('%d.%m.%Y')
                    else:
                        subscription_end_formatted = "ошибка даты"
                except Exception as e:
                    logger.error(f"❌ Ошибка форматирования даты: {e}")
                    subscription_end_formatted = "ошибка"

            return {
                'predictions_count': user_data['predictions_count'],
                'remaining_predictions': remaining_predictions,
                'has_subscription': has_subscription,
                'subscription_type': user_data.get('subscription_type', 'free'),
                'subscription_end': subscription_end_formatted,
                'total_spent': user_data.get('total_spent', 0)
            }

        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики: {e}")
            return None

    def save_prediction(self, telegram_id: int, prediction_type: str, user_name: str,
                        partner_name: str, birth_date: str, zodiac_sign: str,
                        cards: list, prediction: str) -> bool:
        """Сохранить предсказание"""
        try:
            # Получаем пользователя
            user = self._make_request('users', params={'telegram_id': f'eq.{telegram_id}'})
            if not user or len(user) == 0:
                logger.error(f"❌ Пользователь {telegram_id} не найден")
                return False

            user_id = user[0]['id']

            # Создаем предсказание
            prediction_data = {
                'user_id': user_id,
                'prediction_type': prediction_type,
                'user_name': user_name,
                'partner_name': partner_name or '',
                'birth_date': birth_date,
                'zodiac_sign': zodiac_sign,
                'cards_drawn': json.dumps(cards, ensure_ascii=False),
                'prediction_text': prediction,
                'is_ai_generated': True,
                'created_at': datetime.utcnow().isoformat() + 'Z'
            }

            result = self._make_request('predictions', method='POST', data=prediction_data)

            if result:
                # Обновляем счетчик предсказаний пользователя
                update_data = {
                    'predictions_count': user[0]['predictions_count'] + 1,
                    'updated_at': datetime.utcnow().isoformat() + 'Z'
                }

                self._make_request(
                    f'users?id=eq.{user_id}',
                    method='PATCH',
                    data=update_data
                )

                # Обновляем кэш
                cache_key = str(telegram_id)
                if cache_key in self.users_cache:
                    self.users_cache[cache_key]['predictions_count'] += 1

                logger.info(f"✅ Предсказание сохранено для пользователя {telegram_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"❌ Ошибка сохранения предсказания: {e}")
            return False

    def get_user_predictions(self, telegram_id: int, limit: int = 5):
        """Получить историю предсказаний"""
        try:
            # Получаем пользователя
            user = self._make_request('users', params={'telegram_id': f'eq.{telegram_id}'})
            if not user or len(user) == 0:
                return []

            user_id = user[0]['id']

            # Получаем предсказания
            predictions = self._make_request(
                'predictions',
                params={
                    'user_id': f'eq.{user_id}',
                    'order': 'created_at.desc',
                    'limit': str(limit)
                }
            )

            if not predictions:
                return []

            # Преобразуем данные
            result = []
            for pred in predictions:
                result.append({
                    'id': pred['id'],
                    'prediction_type': pred['prediction_type'],
                    'user_name': pred['user_name'],
                    'partner_name': pred['partner_name'],
                    'birth_date': pred['birth_date'],
                    'zodiac_sign': pred['zodiac_sign'],
                    'cards_drawn': json.loads(pred['cards_drawn']),
                    'prediction_text': pred['prediction_text'],
                    'created_at': pred['created_at']
                })

            return result

        except Exception as e:
            logger.error(f"❌ Ошибка получения истории: {e}")
            return []

    def can_user_make_prediction(self, telegram_id: int) -> bool:
        """Проверить может ли пользователь сделать предсказание"""
        stats = self.get_user_stats(telegram_id)
        if not stats:
            return True  # Новый пользователь может сделать предсказание

        return stats['remaining_predictions'] > 0

    def activate_subscription(self, telegram_id: int, subscription_type: str, days: int) -> bool:
        """Активировать подписку"""
        try:
            logger.info(f"🔧 Активация подписки: user={telegram_id}, type={subscription_type}, days={days}")

            user = self._make_request('users', params={'telegram_id': f'eq.{telegram_id}'})
            if not user or len(user) == 0:
                logger.error(f"❌ Пользователь {telegram_id} не найден")
                return False

            user_id = user[0]['id']

            subscription_start = datetime.utcnow()
            subscription_end = subscription_start + timedelta(days=days)

            update_data = {
                'subscription_type': subscription_type,
                'subscription_start': subscription_start.isoformat() + 'Z',
                'subscription_end': subscription_end.isoformat() + 'Z',
                'is_active': True,
                'updated_at': datetime.utcnow().isoformat() + 'Z'
            }

            result = self._make_request(f'users?id=eq.{user_id}', method='PATCH', data=update_data)

            if result:
                logger.info(f"✅ Подписка успешно активирована для {telegram_id} до {subscription_end}")

                # Обновляем кэш
                cache_key = str(telegram_id)
                if cache_key in self.users_cache:
                    self.users_cache[cache_key].update(update_data)

                return True
            else:
                logger.error(f"❌ Не удалось обновить данные пользователя {telegram_id}")
                return False

        except Exception as e:
            logger.error(f"❌ Ошибка активации подписки для {telegram_id}: {e}")
            return False

    def create_payment(self, telegram_id: int, amount: float, payment_system: str,
                       payment_id: str, subscription_type: str, subscription_days: int) -> bool:
        """Создать запись о платеже"""
        try:
            user = self._make_request('users', params={'telegram_id': f'eq.{telegram_id}'})
            if not user or len(user) == 0:
                return False

            user_id = user[0]['id']

            payment_data = {
                'user_id': user_id,
                'amount': amount,
                'currency': 'RUB',
                'payment_system': payment_system,
                'payment_id': payment_id,
                'status': 'completed',
                'subscription_type': subscription_type,
                'subscription_days': subscription_days,
                'created_at': datetime.utcnow().isoformat() + 'Z',
                'completed_at': datetime.utcnow().isoformat() + 'Z'
            }

            result = self._make_request('payments', method='POST', data=payment_data)

            if result:
                # Обновляем total_spent пользователя
                update_data = {
                    'total_spent': user[0].get('total_spent', 0) + amount,
                    'updated_at': datetime.utcnow().isoformat() + 'Z'
                }

                self._make_request(f'users?id=eq.{user_id}', method='PATCH', data=update_data)

                logger.info(f"✅ Платеж сохранен для {telegram_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"❌ Ошибка создания платежа: {e}")
            return False

    # НОВЫЕ МЕТОДЫ ДЛЯ РАБОТЫ С ПОЛЬЗОВАТЕЛЯМИ
    def get_all_users(self, limit: int = 100, offset: int = 0):
        """Получить список всех пользователей"""
        try:
            params = {
                'order': 'created_at.desc',
                'limit': str(limit),
                'offset': str(offset)
            }

            users = self._make_request('users', params=params)
            return users or []

        except Exception as e:
            logger.error(f"❌ Ошибка получения пользователей: {e}")
            return []

    def get_users_count(self):
        """Получить общее количество пользователей"""
        try:
            # Используем Supabase count заголовок
            headers = self.headers.copy()
            headers['Prefer'] = 'count=exact'

            url = f"{self.supabase_url}/users"
            response = requests.get(url, headers=headers, params={'limit': '1'})

            if response.status_code == 200:
                count = response.headers.get('content-range', '').split('/')
                if len(count) > 1:
                    return int(count[1])
            return 0

        except Exception as e:
            logger.error(f"❌ Ошибка получения количества пользователей: {e}")
            return 0

    def get_users_with_subscription(self, subscription_type: str = None):
        """Получить пользователей с подпиской"""
        try:
            params = {'order': 'subscription_end.desc'}
            if subscription_type:
                params['subscription_type'] = f'eq.{subscription_type}'
            else:
                params['subscription_type'] = 'neq.free'

            users = self._make_request('users', params=params)
            return users or []

        except Exception as e:
            logger.error(f"❌ Ошибка получения пользователей с подпиской: {e}")
            return []

    def search_users(self, query: str):
        """Поиск пользователей по имени, username или ID"""
        try:
            # Поиск по telegram_id если query число
            if query.isdigit():
                users_by_id = self._make_request('users', params={'telegram_id': f'eq.{query}'})
                if users_by_id:
                    return users_by_id

            # Поиск по имени и username
            params = {
                'or': f'(first_name.ilike.%{query}%,username.ilike.%{query}%)',
                'order': 'created_at.desc'
            }

            users = self._make_request('users', params=params)
            return users or []

        except Exception as e:
            logger.error(f"❌ Ошибка поиска пользователей: {e}")
            return []

    # МЕТОДЫ ДЛЯ ПОДДЕРЖКИ
    def create_support_ticket(self, user_id: int, user_name: str, message: str, message_type: str = 'question') -> int:
        """Создать тикет поддержки"""
        try:
            ticket_data = {
                'user_id': user_id,
                'user_name': user_name,
                'message': message,
                'message_type': message_type,
                'status': 'open',
                'created_at': datetime.utcnow().isoformat() + 'Z'
            }

            result = self._make_request('support_tickets', method='POST', data=ticket_data)

            if result and len(result) > 0:
                ticket_id = result[0]['id']
                logger.info(f"✅ Создан тикет поддержки #{ticket_id}")
                return ticket_id

            return None

        except Exception as e:
            logger.error(f"❌ Ошибка создания тикета: {e}")
            return None

    def add_support_message(self, ticket_id: int, user_id: int, user_name: str, message: str, is_admin: bool = False):
        """Добавить сообщение в тикет"""
        try:
            # Для админов нужно найти или создать запись пользователя в таблице users
            if is_admin:
                # Получаем пользователя по telegram_id (user_id в этом случае - telegram_id админа)
                admin_user = self._make_request('users', params={'telegram_id': f'eq.{user_id}'})
                if not admin_user or len(admin_user) == 0:
                    # Создаем временную запись админа в users если не существует
                    admin_data = {
                        'telegram_id': user_id,
                        'username': f'admin_{user_id}',
                        'first_name': user_name,
                        'last_name': 'Admin',
                        'language_code': 'ru',
                        'subscription_type': 'admin',
                        'is_active': True,
                        'created_at': datetime.utcnow().isoformat() + 'Z'
                    }
                    admin_user = self._make_request('users', method='POST', data=admin_data)
                    if admin_user and len(admin_user) > 0:
                        actual_user_id = admin_user[0]['id']
                    else:
                        logger.error(f"❌ Не удалось создать запись админа в users")
                        return False
                else:
                    actual_user_id = admin_user[0]['id']
            else:
                actual_user_id = user_id  # Для обычных пользователей используем переданный user_id

            message_data = {
                'ticket_id': ticket_id,
                'user_id': actual_user_id,  # Используем ID из таблицы users
                'user_name': user_name,
                'message': message,
                'is_admin': is_admin,
                'created_at': datetime.utcnow().isoformat() + 'Z'
            }

            result = self._make_request('support_messages', method='POST', data=message_data)

            if result:
                logger.info(f"✅ Добавлено сообщение в тикет #{ticket_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"❌ Ошибка добавления сообщения: {e}")
            return False

    def get_support_tickets(self, status: str = None, user_id: int = None):
        """Получить список тикетов"""
        try:
            params = {}
            if status:
                params['status'] = f'eq.{status}'
            if user_id:
                params['user_id'] = f'eq.{user_id}'
            params['order'] = 'created_at.desc'

            tickets = self._make_request('support_tickets', params=params)
            return tickets or []

        except Exception as e:
            logger.error(f"❌ Ошибка получения тикетов: {e}")
            return []

    def get_ticket_messages(self, ticket_id: int):
        """Получить сообщения тикета"""
        try:
            messages = self._make_request(
                'support_messages',
                params={
                    'ticket_id': f'eq.{ticket_id}',
                    'order': 'created_at.asc'
                }
            )
            return messages or []

        except Exception as e:
            logger.error(f"❌ Ошибка получения сообщений: {e}")
            return []

    def update_ticket_status(self, ticket_id: int, status: str):
        """Обновить статус тикета"""
        try:
            update_data = {
                'status': status,
                'updated_at': datetime.utcnow().isoformat() + 'Z'
            }

            if status == 'closed':
                update_data['closed_at'] = datetime.utcnow().isoformat() + 'Z'

            result = self._make_request(f'support_tickets?id=eq.{ticket_id}', method='PATCH', data=update_data)

            if result:
                logger.info(f"✅ Статус тикета #{ticket_id} изменен на {status}")
                return True

            return False

        except Exception as e:
            logger.error(f"❌ Ошибка обновления статуса: {e}")
            return False

    def get_user_by_id(self, user_id: int):
        """Получить пользователя по ID"""
        try:
            users = self._make_request('users', params={'id': f'eq.{user_id}'})
            return users[0] if users and len(users) > 0 else None
        except Exception as e:
            logger.error(f"❌ Ошибка получения пользователя: {e}")
            return None

    def is_admin(self, user_id: int) -> bool:
        """Проверяет является ли пользователь админом"""
        return user_id in ADMIN_IDS

    # МЕТОДЫ ДЛЯ РАБОТЫ С ПРОМОКОДАМИ
    def create_promo_code(self, code: str, days: int, max_uses: int, created_by: int,
                          description: str = "", subscription_type: str = "premium") -> bool:
        """Создать промокод"""
        try:
            promo_data = {
                'code': code.upper(),
                'subscription_type': subscription_type,
                'days': days,
                'max_uses': max_uses,
                'used_count': 0,
                'is_active': True,
                'created_by': str(created_by),  # Конвертируем в строку для безопасности
                'description': description,
                'created_at': datetime.utcnow().isoformat() + 'Z'
            }

            result = self._make_request('promo_codes', method='POST', data=promo_data)

            if result is None:
                logger.error(f"❌ Не удалось создать промокод {code}")
                return False

            logger.info(f"✅ Промокод создан: {code}")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка создания промокода {code}: {e}")
            return False

    def get_promo_code(self, code: str):
        """Получить промокод по коду"""
        try:
            promos = self._make_request('promo_codes', params={'code': f'eq.{code.upper()}'})
            return promos[0] if promos and len(promos) > 0 else None
        except Exception as e:
            logger.error(f"❌ Ошибка получения промокода: {e}")
            return None

    def use_promo_code(self, code: str, user_id: int) -> bool:
        """Использовать промокод"""
        try:
            logger.info(f"🔑 Попытка активации промокода: {code} для пользователя {user_id}")

            promo = self.get_promo_code(code)
            if not promo:
                logger.error(f"❌ Промокод {code} не найден")
                return False

            logger.info(f"📋 Найден промокод: {promo}")

            # Проверяем активность промокода
            if not promo.get('is_active', True):
                logger.error(f"❌ Промокод {code} не активен")
                return False

            # Проверяем лимит использований
            used_count = promo.get('used_count', 0)
            max_uses = promo.get('max_uses', 1)

            if used_count >= max_uses:
                logger.error(f"❌ Промокод {code} уже использован максимальное количество раз ({used_count}/{max_uses})")
                return False

            # Проверяем срок действия
            if promo.get('expires_at'):
                expires_date = self._parse_supabase_date(promo['expires_at'])
                if expires_date and expires_date < datetime.utcnow():
                    logger.error(f"❌ Срок действия промокода {code} истек")
                    return False

            # Получаем параметры подписки из промокода
            subscription_type = promo.get('subscription_type', 'premium')
            days = promo.get('days', 30)

            logger.info(f"🎯 Активация подписки: тип={subscription_type}, дней={days}")

            # Активируем подписку
            success = self.activate_subscription(user_id, subscription_type, days)

            if success:
                logger.info(f"✅ Подписка активирована для пользователя {user_id}")

                # Обновляем счетчик использований промокода
                update_data = {
                    'used_count': used_count + 1,
                    'updated_at': datetime.utcnow().isoformat() + 'Z'
                }

                # Если достигли лимита, деактивируем код
                if update_data['used_count'] >= max_uses:
                    update_data['is_active'] = False
                    logger.info(f"🔒 Промокод {code} деактивирован (достигнут лимит)")

                update_result = self._make_request(f'promo_codes?id=eq.{promo["id"]}', method='PATCH', data=update_data)

                if update_result:
                    logger.info(f"✅ Счетчик промокода {code} обновлен")
                else:
                    logger.error(f"❌ Не удалось обновить счетчик промокода {code}")

                return True
            else:
                logger.error(f"❌ Не удалось активировать подписку для пользователя {user_id}")
                return False

        except Exception as e:
            logger.error(f"❌ Критическая ошибка использования промокода {code}: {e}")
            return False

    def get_all_promo_codes(self):
        """Получить все промокоды"""
        try:
            promos = self._make_request('promo_codes', params={'order': 'created_at.desc'})
            return promos or []
        except Exception as e:
            logger.error(f"❌ Ошибка получения промокодов: {e}")
            return []

    def deactivate_promo_code(self, code_id: int) -> bool:
        """Деактивировать промокод"""
        try:
            update_data = {
                'is_active': False,
                'updated_at': datetime.utcnow().isoformat() + 'Z'
            }
            result = self._make_request(f'promo_codes?id=eq.{code_id}', method='PATCH', data=update_data)
            return result is not None
        except Exception as e:
            logger.error(f"❌ Ошибка деактивации промокода: {e}")
            return False

    def get_promo_stats(self):
        """Получить статистику по промокодам"""
        try:
            promos = self.get_all_promo_codes()

            total = len(promos)
            active = sum(1 for p in promos if p['is_active'])
            used = sum(1 for p in promos if p['used_count'] > 0)
            total_uses = sum(p['used_count'] for p in promos)

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