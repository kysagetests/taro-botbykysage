import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ConversationHandler
from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, Update
from database_manager import DatabaseManager
from openrouter_api import OpenRouterAssistant
import json
from dateutil import parser
from datetime import datetime, timedelta
import asyncio
from config import FREE_PREDICTIONS_LIMIT, SUBSCRIPTION_PRICE, ADMIN_IDS

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
ADMIN_RESPONSE = range(1)


class TarotBot:
    def __init__(self, token: str, openrouter_key: str, model: str):
        self.application = Application.builder().token(token).build()
        self.database = DatabaseManager()
        self.ai_assistant = OpenRouterAssistant(openrouter_key, model)
        self.setup_handlers()

    async def activate_promo_command(self, update: Update, context):
        """Команда для прямой активации промокода"""
        user = update.effective_user

        if not context.args:
            await update.message.reply_text(
                "🔑 *АКТИВАЦИЯ ПРОМОКОДА*\n\n"
                "Использование:\n"
                "`/activate_promo КОД`\n\n"
                "*Пример:*\n"
                "`/activate_promo TAROT2024`",
                parse_mode='Markdown'
            )
            return

        code = context.args[0].strip().upper()
        logger.info(f"🔑 Прямая активация промокода {code} для пользователя {user.id}")

        success = self.database.use_promo_code(code, user.id)

        if success:
            await update.message.reply_text(
                "✅ *Промокод активирован!*\n\n"
                "Ваша подписка успешно активирована! 🎉",
                parse_mode='Markdown',
                reply_markup=self.get_main_keyboard()
            )
        else:
            await update.message.reply_text(
                "❌ *Неверный промокод или он уже использован*",
                parse_mode='Markdown',
                reply_markup=self.get_main_keyboard()
            )

    def setup_handlers(self):
        # Команды
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("profile", self.profile))
        self.application.add_handler(CommandHandler("subscription", self.subscription))
        self.application.add_handler(CommandHandler("history", self.history))
        self.application.add_handler(CommandHandler("help", self.help))
        self.application.add_handler(CommandHandler("support", self.support))
        self.application.add_handler(CommandHandler("activate_promo", self.activate_promo_command))

        # Админ команды
        self.application.add_handler(CommandHandler("admin", self.admin_panel))
        self.application.add_handler(CommandHandler("tickets", self.list_tickets))
        self.application.add_handler(CommandHandler("users", self.admin_users))
        self.application.add_handler(CommandHandler("users_list", self.users_list))
        self.application.add_handler(CommandHandler("users_search", self.users_search))
        self.application.add_handler(CommandHandler("users_premium", self.users_premium))
        self.application.add_handler(CommandHandler("users_stats", self.users_stats))
        self.application.add_handler(CommandHandler("broadcast", self.broadcast_message))
        self.application.add_handler(CommandHandler("broadcast_premium", self.broadcast_premium))
        self.application.add_handler(CommandHandler("broadcast_free", self.broadcast_free))
        self.application.add_handler(CommandHandler("send_to_user", self.send_to_user_menu))

        # Промокод команды
        self.application.add_handler(CommandHandler("create_promo", self.create_promo_command))
        self.application.add_handler(CommandHandler("list_promos", self.list_promos_command))
        self.application.add_handler(CommandHandler("promo_stats", self.promo_stats_command))

        # Conversation Handler для ответов админа
        admin_conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.start_admin_response, pattern='^respond_')],
            states={
                ADMIN_RESPONSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_admin_response)]
            },
            fallbacks=[CommandHandler("cancel", self.cancel_admin_response)]
        )
        self.application.add_handler(admin_conv)

        # Сообщения
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

        # Callback кнопки
        self.application.add_handler(CallbackQueryHandler(self.button_handler))

    def get_main_keyboard(self):
        keyboard = [
            [KeyboardButton("🔮 Сделать расклад"), KeyboardButton("👤 Профиль")],
            [KeyboardButton("📚 История"), KeyboardButton("💎 Подписка")],
            [KeyboardButton("🆘 Поддержка")]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    def get_spreads_keyboard(self):
        keyboard = [
            [KeyboardButton("🔮 Личный расклад")],
            [KeyboardButton("💼 Карьерный расклад")],
            [KeyboardButton("❤️ Совместимость")],
            [KeyboardButton("🔥 Секс и страсть")],
            [KeyboardButton("🔙 Основное меню")]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    def get_admin_keyboard(self):
        keyboard = [
            [KeyboardButton("📊 Статистика"), KeyboardButton("🎫 Тикеты")],
            [KeyboardButton("👥 Пользователи"), KeyboardButton("📢 Рассылка")],
            [KeyboardButton("🎫 Промокоды"), KeyboardButton("🔮 Основное меню")]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    def get_users_management_keyboard(self):
        keyboard = [
            [KeyboardButton("📋 Список пользователей"), KeyboardButton("🔍 Поиск пользователя")],
            [KeyboardButton("💎 Премиум пользователи"), KeyboardButton("📊 Статистика")],
            [KeyboardButton("📨 Отправить сообщение"), KeyboardButton("🔙 В админ панель")]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    def get_broadcast_keyboard(self):
        keyboard = [
            [KeyboardButton("📢 Всем пользователям"), KeyboardButton("💎 Только премиум")],
            [KeyboardButton("🆓 Только бесплатным"), KeyboardButton("🔙 В админ панель")]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    def get_promo_management_keyboard(self):
        """Клавиатура управления промокодами"""
        try:
            keyboard = [
                [KeyboardButton("📋 Список кодов")],
                [KeyboardButton("➕ Создать коды")],
                [KeyboardButton("📊 Статистика")],
                [KeyboardButton("🔙 В админ панель")]
            ]
            return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        except Exception as e:
            logger.error(f"❌ Ошибка создания клавиатуры: {e}")
            # Возвращаем простую клавиатуру в случае ошибки
            keyboard = [
                [KeyboardButton("🔙 В админ панель")]
            ]
            return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    def get_promo_management_keyboard(self):
        keyboard = [
            [KeyboardButton("📋 Список кодов"), KeyboardButton("➕ Создать коды")],
            [KeyboardButton("📊 Статистика"), KeyboardButton("🔙 В админ панель")]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    def get_support_keyboard(self):
        keyboard = [[KeyboardButton("❌ Отмена")]]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    def is_admin(self, user_id: int) -> bool:
        """Проверяет является ли пользователь админом"""
        return user_id in ADMIN_IDS

    async def start(self, update, context):
        user = update.effective_user
        db_user = self.database.get_or_create_user(user)

        welcome_text = f"""
🔮 *Добро пожаловать в Цифровое Таро, {user.first_name}!* 

✨ *Используйте кнопки ниже для навигации:*

🔮 *Сделать расклад* - выбор типа гадания
👤 *Профиль* - ваша статистика и настройки  
📚 *История* - архив предыдущих предсказаний
💎 *Подписка* - информация о премиум доступе
🆘 *Поддержка* - помощь и консультации

📊 *Ваша статистика:*
• Сделано предсказаний: {db_user['predictions_count']}/{FREE_PREDICTIONS_LIMIT}
• Статус: {self._get_user_status_text(db_user)}

*Начните с выбора расклада!* ⬇️
        """

        await update.message.reply_text(
            welcome_text,
            parse_mode='Markdown',
            reply_markup=self.get_main_keyboard()
        )

    async def show_spreads_menu(self, update, context):
        """Показать меню раскладов"""
        user = update.effective_user
        db_user = self.database.get_or_create_user(user)

        stats = self.database.get_user_stats(db_user['telegram_id'])

        menu_text = f"""
🔮 *ВЫБЕРИТЕ ТИП РАСКЛАДА*

*Доступные расклады:*

🔮 *Личный расклад* - предсказание для вас лично, самопознание и личностный рост

💼 *Карьерный расклад* - прогноз профессионального развития, финансы и успех

❤️ *Совместимость* - анализ отношений с партнером, любовь и гармония

🔥 *Секс и страсть* - интимная сфера, страсть и энергетика близости

📊 *Ваша статистика:*
• Сделано предсказаний: {stats['predictions_count']}
• Осталось бесплатных: {stats['remaining_predictions']}
• Статус: {self._get_user_status_text(db_user)}

*Выберите тип расклада ниже ⬇️*
        """

        await update.message.reply_text(
            menu_text,
            parse_mode='Markdown',
            reply_markup=self.get_spreads_keyboard()
        )

    async def show_spreads_menu_from_callback(self, query, context):
        """Показать меню раскладов из callback"""
        user = query.from_user
        db_user = self.database.get_or_create_user(user)

        stats = self.database.get_user_stats(db_user['telegram_id'])

        menu_text = f"""
🔮 *ВЫБЕРИТЕ ТИП РАСКЛАДА*

*Доступные расклады:*

🔮 *Личный расклад* - предсказание для вас лично, самопознание и личностный рост

💼 *Карьерный расклад* - прогноз профессионального развития, финансы и успех

❤️ *Совместимость* - анализ отношений с партнером, любовь и гармония

🔥 *Секс и страсть* - интимная сфера, страсть и энергетика близости

📊 *Ваша статистика:*
• Сделано предсказаний: {stats['predictions_count']}
• Осталось бесплатных: {stats['remaining_predictions']}
• Статус: {self._get_user_status_text(db_user)}

*Выберите тип расклада ниже ⬇️*
        """

        await query.edit_message_text(
            menu_text,
            parse_mode='Markdown',
            reply_markup=self.get_spreads_keyboard()
        )

    async def show_main_menu(self, update, context):
        """Вернуться в основное меню"""
        await update.message.reply_text(
            "🔮 Возврат в основное меню",
            reply_markup=self.get_main_keyboard()
        )

    async def show_main_menu_from_callback(self, query, context):
        """Вернуться в основное меню из callback"""
        await query.edit_message_text(
            "🔮 Возврат в основное меню",
            reply_markup=self.get_main_keyboard()
        )

    async def handle_message(self, update, context):
        user = update.effective_user
        user_message = update.message.text

        # Проверяем, ожидается ли сообщение в поддержку
        if context.user_data.get('awaiting_support'):
            await self.handle_support_message(update, context)
            return

        # Проверяем, ожидается ли промокод
        if context.user_data.get('awaiting_promo_code'):
            context.user_data['awaiting_promo_code'] = False
            await self.handle_promo_code_input(update, context)
            return

        # Проверяем, ожидается ли поиск пользователей
        if context.user_data.get('awaiting_user_search'):
            context.user_data['awaiting_user_search'] = False
            await self._perform_users_search(update, context, user_message)
            return

        # Проверяем, ожидается ли сообщение для рассылки
        if context.user_data.get('awaiting_broadcast_message'):
            context.user_data['awaiting_broadcast_message'] = False
            target = context.user_data.get('broadcast_target', 'all')
            await self._start_broadcast(update, context, user_message, target)
            return

        # Проверяем, ожидается ли ID пользователя для отправки сообщения
        if context.user_data.get('awaiting_user_id'):
            await self.handle_user_id_input(update, context)
            return

        # Проверяем, ожидается ли сообщение для конкретного пользователя
        if context.user_data.get('awaiting_user_message'):
            await self.handle_user_message_input(update, context)
            return

        # Получаем или создаем пользователя
        db_user = self.database.get_or_create_user(user)
        if not db_user:
            await update.message.reply_text("❌ Ошибка загрузки профиля")
            return

        # Обработка основных команд через кнопки
        if user_message == "🔮 Сделать расклад":
            await self.show_spreads_menu(update, context)
        elif user_message == "🔮 Личный расклад":
            await self.start_personal_prediction(update, context)
        elif user_message == "💼 Карьерный расклад":
            await self.start_career_prediction(update, context)
        elif user_message == "❤️ Совместимость":
            await self.start_compatibility_prediction(update, context)
        elif user_message == "🔥 Секс и страсть":
            await self.start_intimacy_prediction(update, context)
        elif user_message == "🔙 Основное меню":
            await self.show_main_menu(update, context)
        elif user_message == "👤 Профиль":
            await self.profile(update, context)
        elif user_message == "📚 История":
            await self.history(update, context)
        elif user_message == "💎 Подписка":
            await self.subscription(update, context)
        elif user_message == "🆘 Поддержка":
            await self.support(update, context)

        # Админ команды через кнопки
        elif user_message == "📊 Статистика" and self.is_admin(user.id):
            await self.admin_stats(update, context)
        elif user_message == "🎫 Тикеты" and self.is_admin(user.id):
            await self.list_tickets(update, context)
        elif user_message == "👥 Пользователи" and self.is_admin(user.id):
            await self.admin_users(update, context)
        elif user_message == "🎫 Промокоды" and self.is_admin(user.id):
            await self.promo_management(update, context)
        elif user_message == "📢 Рассылка" and self.is_admin(user.id):
            await self.broadcast_menu(update, context)
        elif user_message == "🎫 Промокоды" and self.is_admin(user.id):
            await self.promo_management(update, context)
        elif user_message == "🔮 Основное меню" and self.is_admin(user.id):
            await update.message.reply_text(
                "🔙 Возврат в основное меню",
                reply_markup=self.get_main_keyboard()
            )

        # Управление пользователями через кнопки
        elif user_message == "📋 Список пользователей" and self.is_admin(user.id):
            await self.users_list(update, context)
        elif user_message == "🔍 Поиск пользователя" and self.is_admin(user.id):
            await self.users_search_menu(update, context)
        elif user_message == "💎 Премиум пользователи" and self.is_admin(user.id):
            await self.users_premium(update, context)
        elif user_message == "📊 Статистика" and self.is_admin(user.id):
            await self.users_stats(update, context)
        elif user_message == "📨 Отправить сообщение" and self.is_admin(user.id):
            await self.send_to_user_menu(update, context)
        elif user_message == "🔙 В админ панель" and self.is_admin(user.id):
            await self.admin_panel(update, context)

        # Управление промокодами через кнопки
        elif user_message == "📋 Список кодов" and self.is_admin(user.id):
            await self.list_promos_command(update, context)
        elif user_message == "➕ Создать коды" and self.is_admin(user.id):
            await self.create_promo_menu(update, context)
        elif user_message == "📊 Статистика" and self.is_admin(user.id):
            await self.promo_stats_command(update, context)

        # Рассылка через кнопки
        elif user_message == "📢 Всем пользователям" and self.is_admin(user.id):
            context.user_data['awaiting_broadcast_message'] = True
            context.user_data['broadcast_target'] = 'all'
            await update.message.reply_text(
                "📢 *РАССЫЛКА ВСЕМ ПОЛЬЗОВАТЕЛЯМ*\n\n"
                "Введите сообщение для рассылки:",
                parse_mode='Markdown'
            )
        elif user_message == "💎 Только премиум" and self.is_admin(user.id):
            context.user_data['awaiting_broadcast_message'] = True
            context.user_data['broadcast_target'] = 'premium'
            await update.message.reply_text(
                "💎 *РАССЫЛКА ПРЕМИУМ ПОЛЬЗОВАТЕЛЯМ*\n\n"
                "Введите сообщение для рассылки:",
                parse_mode='Markdown'
            )
        elif user_message == "🆓 Только бесплатным" and self.is_admin(user.id):
            context.user_data['awaiting_broadcast_message'] = True
            context.user_data['broadcast_target'] = 'free'
            await update.message.reply_text(
                "🆓 *РАССЫЛКА БЕСПЛАТНЫМ ПОЛЬЗОВАТЕЛЯМ*\n\n"
                "Введите сообщение для рассылки:",
                parse_mode='Markdown'
            )

        elif user_message == "❌ Отмена":
            # Сбрасываем режим поддержки если активен
            if context.user_data.get('awaiting_support'):
                context.user_data['awaiting_support'] = False
                await update.message.reply_text(
                    "❌ Обращение в поддержку отменено.",
                    reply_markup=self.get_main_keyboard()
                )
            elif context.user_data.get('awaiting_promo_code'):
                context.user_data['awaiting_promo_code'] = False
                await update.message.reply_text(
                    "❌ Активация промокода отменена.",
                    reply_markup=self.get_subscription_keyboard()
                )
            else:
                await update.message.reply_text(
                    "❌ Нечего отменять.",
                    reply_markup=self.get_main_keyboard()
                )
        else:
            # Обработка ввода данных для предсказания
            await self.process_prediction_input(update, context, user_message)

    async def start_personal_prediction(self, update, context):
        """Начало личного расклада"""
        user = update.effective_user
        db_user = self.database.get_or_create_user(user)

        if not self.database.can_user_make_prediction(db_user['telegram_id']):
            await self._show_subscription_required(update, db_user)
            return

        context.user_data['current_prediction_type'] = 'personal'

        await update.message.reply_text(
            "🔮 *Личный расклад*\n\n"
            "Напишите ваше *имя* и *дату рождения*:\n"
            "*Пример:* Анна 15.03.1990\n\n"
            f"🎯 *Осталось бесплатных предсказаний:* {self.database.get_user_stats(db_user['telegram_id'])['remaining_predictions']}",
            parse_mode='Markdown'
        )

    async def start_career_prediction(self, update, context):
        """Начало карьерного расклада"""
        user = update.effective_user
        db_user = self.database.get_or_create_user(user)

        if not self.database.can_user_make_prediction(db_user['telegram_id']):
            await self._show_subscription_required(update, db_user)
            return

        context.user_data['current_prediction_type'] = 'career'

        await update.message.reply_text(
            "💼 *Карьерный расклад*\n\n"
            "Напишите ваше *имя* и *дату рождения*:\n"
            "*Пример:* Анна 15.03.1990\n\n"
            f"🎯 *Осталось бесплатных предсказаний:* {self.database.get_user_stats(db_user['telegram_id'])['remaining_predictions']}",
            parse_mode='Markdown'
        )

    async def start_compatibility_prediction(self, update, context):
        """Начало расклада на совместимость"""
        user = update.effective_user
        db_user = self.database.get_or_create_user(user)

        if not self.database.can_user_make_prediction(db_user['telegram_id']):
            await self._show_subscription_required(update, db_user)
            return

        context.user_data['current_prediction_type'] = 'compatibility'

        await update.message.reply_text(
            "❤️ *Расклад на совместимость*\n\n"
            "Напишите через пробел:\n"
            "*ВашеИмя ИмяПартнера ВашаДатаРождения*\n"
            "*Пример:* Анна Иван 15.03.1990\n\n"
            f"🎯 *Осталось бесплатных предсказаний:* {self.database.get_user_stats(db_user['telegram_id'])['remaining_predictions']}",
            parse_mode='Markdown'
        )

    async def start_intimacy_prediction(self, update, context):
        """Начало расклада на секс и страсть"""
        user = update.effective_user
        db_user = self.database.get_or_create_user(user)

        if not self.database.can_user_make_prediction(db_user['telegram_id']):
            await self._show_subscription_required(update, db_user)
            return

        context.user_data['current_prediction_type'] = 'intimacy'

        await update.message.reply_text(
            "🔥 *Расклад на секс и страсть*\n\n"
            "Напишите через пробел:\n"
            "*ВашеИмя ИмяПартнера ВашаДатаРождения*\n"
            "*Пример:* Анна Иван 15.03.1990\n\n"
            f"🎯 *Осталось бесплатных предсказаний:* {self.database.get_user_stats(db_user['telegram_id'])['remaining_predictions']}",
            parse_mode='Markdown'
        )

    async def process_prediction_input(self, update, context, user_message):
        """Обработка введенных данных для предсказания"""
        user = update.effective_user
        db_user = self.database.get_or_create_user(user)

        prediction_type = context.user_data.get('current_prediction_type')
        if not prediction_type:
            await update.message.reply_text(
                "❌ Сначала выберите тип расклада из меню",
                reply_markup=self.get_spreads_keyboard()
            )
            return

        try:
            parts = user_message.split()

            if prediction_type in ['compatibility', 'intimacy']:
                if len(parts) < 3:
                    await update.message.reply_text(
                        "❌ *Неверный формат*\n\n"
                        f"Для расклада {self._get_prediction_type_name(prediction_type)} нужно:\n"
                        "*ВашеИмя ИмяПартнера ДатаРождения*\n"
                        "*Пример:* Анна Иван 15.03.1990",
                        parse_mode='Markdown'
                    )
                    return

                name = parts[0]
                partner_name = parts[1]
                birth_date_str = ' '.join(parts[2:])
            else:
                if len(parts) < 2:
                    await update.message.reply_text(
                        "❌ *Неверный формат*\n\n"
                        "Напишите: *Имя ДатаРождения*\n"
                        "*Пример:* Анна 15.03.1990",
                        parse_mode='Markdown'
                    )
                    return

                name = parts[0]
                partner_name = ""
                birth_date_str = ' '.join(parts[1:])

            # Парсим дату
            try:
                birth_date = parser.parse(birth_date_str, dayfirst=True)
                birth_date_formatted = birth_date.strftime("%d.%m.%Y")
                zodiac_sign = self.ai_assistant.get_zodiac_sign(birth_date)
            except Exception as e:
                await update.message.reply_text(
                    "❌ *Неверный формат даты*\n\n"
                    "Попробуйте: *ДД.ММ.ГГГГ*\n"
                    "*Пример:* 15.03.1990",
                    parse_mode='Markdown'
                )
                return

            # Выбираем карты
            cards = self.ai_assistant.draw_cards(3)

            # Показываем процесс
            analyzing_msg = await update.message.reply_text(
                f"🎴 *Выпали карты:* {', '.join(cards)}\n\n"
                f"🔮 *Соединяюсь с энергиями карт...* 🌙\n"
                f"*Расшифровываю символы и знаки...* ✨",
                parse_mode='Markdown'
            )

            # Получаем предсказание
            try:
                prediction = await asyncio.wait_for(
                    self.ai_assistant.generate_tarot_prediction(
                        prediction_type, name, partner_name, birth_date_formatted, zodiac_sign, cards
                    ),
                    timeout=30.0
                )
            except asyncio.TimeoutError:
                prediction = self.ai_assistant._get_truly_random_fallback(
                    prediction_type, name, partner_name, cards, zodiac_sign
                )
                await analyzing_msg.edit_text("⏰ *Энергии карт требуют больше времени для раскрытия...*")

            # Сохраняем данные
            self.database.save_prediction(
                db_user['telegram_id'], prediction_type, name, partner_name,
                birth_date_formatted, zodiac_sign, cards, prediction
            )

            # Формируем ответ
            title = self._get_prediction_title(prediction_type, name, partner_name)

            response_text = f"""
{title}

*📅 Дата рождения:* {birth_date_formatted}
*♈ Знак зодиака:* {zodiac_sign}
*🎴 Карты:* {', '.join(cards)}

{prediction}

*✨ {self._get_prediction_footer(db_user)}*
            """

            # Сохраняем для расширенного обоснования
            context.user_data['last_prediction'] = {
                'prediction_type': prediction_type,
                'name': name,
                'partner_name': partner_name,
                'birth_date': birth_date_formatted,
                'zodiac_sign': zodiac_sign,
                'cards': cards,
                'prediction': prediction
            }

            await analyzing_msg.delete()
            await update.message.reply_text(
                response_text,
                parse_mode='Markdown',
                reply_markup=self.get_prediction_keyboard()
            )

            # Очищаем тип предсказания
            context.user_data['current_prediction_type'] = None

        except Exception as e:
            logger.error(f"❌ Ошибка предсказания: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка. Попробуйте еще раз.",
                reply_markup=self.get_spreads_keyboard()
            )

    def _get_prediction_type_name(self, prediction_type):
        """Получить человекочитаемое название типа предсказания"""
        names = {
            'personal': 'Личный расклад',
            'career': 'Карьерный расклад',
            'compatibility': 'Совместимость',
            'intimacy': 'Секс и страсть'
        }
        return names.get(prediction_type, 'расклад')

    def _get_prediction_title(self, prediction_type, name, partner_name):
        """Получить заголовок для предсказания"""
        titles = {
            'personal': f"🔮 ЛИЧНЫЙ РАСКЛАД ДЛЯ {name}",
            'career': f"💼 КАРЬЕРНЫЙ РАСКЛАД ДЛЯ {name}",
            'compatibility': f"❤️ СОВМЕСТИМОСТЬ: {name} и {partner_name}",
            'intimacy': f"🔥 СЕКС И СТРАСТЬ: {name} и {partner_name}"
        }
        return titles.get(prediction_type, f"🔮 РАСКЛАД ДЛЯ {name}")

    async def profile(self, update, context):
        """Показать профиль пользователя"""
        user = update.effective_user
        stats = self.database.get_user_stats(user.id)

        if not stats:
            await update.message.reply_text("❌ Ошибка загрузки профиля")
            return

        profile_text = f"""
👤 *ВАШ ПРОФИЛЬ*

*📊 Статистика:*
• Предсказаний сделано: {stats['predictions_count']}
• Осталось бесплатных: {stats['remaining_predictions']}
• Всего потрачено: {stats['total_spent']}₽

*💎 Подписка:*
• Статус: {self._get_subscription_status(stats)}
• Тип: {stats['subscription_type']}
• {self._get_subscription_date(stats)}

*🆔 Ваш ID:* {user.id}
        """

        if update.callback_query:
            await update.callback_query.edit_message_text(
                profile_text,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                profile_text,
                parse_mode='Markdown',
                reply_markup=self.get_main_keyboard()
            )

    async def subscription(self, update, context):
        """Показать информацию о подписке"""
        user = update.effective_user
        stats = self.database.get_user_stats(user.id)

        if not stats:
            await update.message.reply_text("❌ Ошибка загрузки данных")
            return

        subscription_text = f"""
💎 *ПОДПИСКА НА ТАРО*

*Ваш статус:* {self._get_subscription_status(stats)}

*🆓 Бесплатный доступ:*
• {FREE_PREDICTIONS_LIMIT} предсказаний
• Все типы раскладов
• Базовые предсказания

*💎 ПРЕМИУМ ПОДПИСКА ({SUBSCRIPTION_PRICE}₽/месяц):*
• Неограниченные предсказания
• Расширенные обоснования
• Приоритетная обработка
• Поддержка 24/7
• Все типы раскладов

*📊 Ваша статистика:*
• Сделано предсказаний: {stats['predictions_count']}
• Осталось бесплатных: {stats['remaining_predictions']}
        """

        if update.callback_query:
            await update.callback_query.edit_message_text(
                subscription_text,
                parse_mode='Markdown',
                reply_markup=self.get_subscription_keyboard()
            )
        else:
            await update.message.reply_text(
                subscription_text,
                parse_mode='Markdown',
                reply_markup=self.get_subscription_keyboard()
            )

    async def history(self, update, context):
        """Показать историю предсказаний"""
        user = update.effective_user
        history = self.database.get_user_predictions(user.id)

        if not history:
            await update.message.reply_text(
                "📚 *У вас еще нет предсказаний*\n\n"
                "Получите первое предсказание! 🔮",
                parse_mode='Markdown'
            )
            return

        response = "📚 *ИСТОРИЯ ПРЕДСКАЗАНИЙ*\n\n"
        for i, pred in enumerate(history[:5], 1):
            type_emoji = self._get_prediction_emoji(pred['prediction_type'])
            cards = pred['cards_drawn']
            response += f"*{i}. {pred['created_at'][:10]}* {type_emoji}\n"
            response += f"🎴 {', '.join(cards)}\n"
            if pred['partner_name']:
                response += f"👥 {pred['user_name']} + {pred['partner_name']}\n"
            else:
                response += f"👤 {pred['user_name']}\n"
            response += f"---\n"

        await update.message.reply_text(response, parse_mode='Markdown')

    def _get_prediction_emoji(self, prediction_type):
        """Получить эмодзи для типа предсказания"""
        emojis = {
            'personal': '🔮',
            'career': '💼',
            'compatibility': '❤️',
            'intimacy': '🔥'
        }
        return emojis.get(prediction_type, '🔮')

    async def help(self, update, context):
        """Показать помощь"""
        help_text = f"""
📖 *ПОМОЩЬ*

*🎯 Типы раскладов:*
• *🔮 Личный расклад* - предсказание для вас лично
• *💼 Карьерный расклад* - прогноз профессионального развития  
• *❤️ Совместимость* - анализ отношений с партнером
• *🔥 Секс и страсть* - интимная сфера и энергетика близости

*💎 Система подписок:*
• *Бесплатно:* {FREE_PREDICTIONS_LIMIT} предсказаний
• *Премиум:* {SUBSCRIPTION_PRICE}₽/месяц (неограниченно)

*👤 Команды:*
/start - начать работу
/profile - ваш профиль  
/subscription - управление подпиской
/history - история предсказаний
/support - служба поддержки
/help - эта справка
        """

        await update.message.reply_text(help_text, parse_mode='Markdown')

    # НОВЫЕ МЕТОДЫ ДЛЯ ПОДДЕРЖКИ
    async def support(self, update: Update, context):
        """Начало диалога с поддержкой"""
        user = update.effective_user

        # Устанавливаем флаг ожидания сообщения поддержки
        context.user_data['awaiting_support'] = True

        await update.message.reply_text(
            "🆘 *СЛУЖБА ПОДДЕРЖКИ*\n\n"
            "Опишите вашу проблему или вопрос, и мы обязательно вам поможем!\n\n"
            "Просто напишите ваше сообщение ниже 👇\n\n"
            "Для отмены нажмите кнопку '❌ Отмена' или напишите 'отмена'",
            parse_mode='Markdown',
            reply_markup=self.get_support_keyboard()
        )

    async def handle_support_message(self, update: Update, context):
        """Обработка сообщения в поддержку"""
        user = update.effective_user
        message_text = update.message.text

        if message_text.lower() in ['отмена', 'cancel', '❌ отмена']:
            context.user_data['awaiting_support'] = False
            await update.message.reply_text(
                "❌ Обращение в поддержку отменено.",
                reply_markup=self.get_main_keyboard()
            )
            return

        # Получаем пользователя
        db_user = self.database.get_or_create_user(user)
        if not db_user:
            await update.message.reply_text("❌ Ошибка загрузки профиля")
            context.user_data['awaiting_support'] = False
            return

        # Создаем тикет
        ticket_id = self.database.create_support_ticket(
            db_user['id'],
            f"{user.first_name} ({user.id})",
            message_text
        )

        if ticket_id:
            # Добавляем сообщение в тикет
            self.database.add_support_message(ticket_id, db_user['id'], user.first_name, message_text)

            # Уведомляем админов
            await self.notify_admins_about_ticket(ticket_id, user, message_text)

            # Сбрасываем флаг
            context.user_data['awaiting_support'] = False

            await update.message.reply_text(
                f"✅ *Ваше сообщение отправлено!*\n\n"
                f"Мы ответим вам в ближайшее время ⏰\n\n"
                f"Для нового обращения используйте /support",
                parse_mode='Markdown',
                reply_markup=self.get_main_keyboard()
            )
        else:
            await update.message.reply_text(
                "❌ Не удалось отправить сообщение. Попробуйте позже.",
                reply_markup=self.get_main_keyboard()
            )

    async def notify_admins_about_ticket(self, ticket_id: int, user, message: str):
        """Уведомляет админов о новом тикете"""
        notification_text = (
            f"🎫 *НОВЫЙ ТИКЕТ ПОДДЕРЖКИ* #{ticket_id}\n\n"
            f"👤 *Пользователь:* {user.first_name}\n"
            f"🆔 *ID:* {user.id}\n"
            f"📝 *Сообщение:* {message}\n\n"
            f"💬 *Для ответа нажмите кнопку ниже:*"
        )

        for admin_id in ADMIN_IDS:
            try:
                keyboard = [[InlineKeyboardButton(
                    f"Ответить на #{ticket_id}",
                    callback_data=f"respond_{ticket_id}"
                )]]

                await self.application.bot.send_message(
                    chat_id=admin_id,
                    text=notification_text,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except Exception as e:
                logger.error(f"❌ Не удалось уведомить админа {admin_id}: {e}")

    # АДМИН МЕТОДЫ
    async def admin_panel(self, update: Update, context):
        """Панель администратора"""
        user = update.effective_user

        if not self.is_admin(user.id):
            await update.message.reply_text("❌ У вас нет доступа к этой команде")
            return

        stats = self.get_admin_stats()

        admin_text = (
            f"👑 *ПАНЕЛЬ АДМИНИСТРАТОРА*\n\n"
            f"📊 *Статистика:*\n"
            f"• Всего пользователей: {stats['total_users']}\n"
            f"• Активных подписок: {stats['active_subscriptions']}\n"
            f"• Открытых тикетов: {stats['open_tickets']}\n"
            f"• Всего предсказаний: {stats['total_predictions']}\n\n"
            f"⚡ *Управление через кнопки ниже:*"
        )

        await update.message.reply_text(
            admin_text,
            parse_mode='Markdown',
            reply_markup=self.get_admin_keyboard()
        )

    async def admin_users(self, update: Update, context):
        """Управление пользователями"""
        user = update.effective_user

        if not self.is_admin(user.id):
            await update.message.reply_text("❌ У вас нет доступа к этой команде")
            return

        users_count = self.database.get_users_count()

        users_text = (
            f"👥 *УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ*\n\n"
            f"📊 Всего пользователей: {users_count}\n\n"
            f"⚡ *Выберите действие через кнопки:*"
        )

        await update.message.reply_text(
            users_text,
            parse_mode='Markdown',
            reply_markup=self.get_users_management_keyboard()
        )

    async def broadcast_menu(self, update: Update, context):
        """Меню рассылки"""
        user = update.effective_user

        if not self.is_admin(user.id):
            await update.message.reply_text("❌ У вас нет доступа к этой команде")
            return

        broadcast_text = (
            f"📢 *РАССЫЛКА СООБЩЕНИЙ*\n\n"
            f"⚡ *Выберите тип рассылки:*\n\n"
            f"• *Всем пользователям* - массовая рассылка\n"
            f"• *Только премиум* - для платных пользователей\n"
            f"• *Только бесплатным* - для бесплатных пользователей"
        )

        await update.message.reply_text(
            broadcast_text,
            parse_mode='Markdown',
            reply_markup=self.get_broadcast_keyboard()
        )

    async def promo_management(self, update: Update, context):
        """Управление промокодами"""
        user = update.effective_user

        if not self.is_admin(user.id):
            await update.message.reply_text("❌ У вас нет доступа к этой команде")
            return

        try:
            from promo_manager import PromoCodeManager
            promo_manager = PromoCodeManager(self.database)
            stats = promo_manager.get_promo_stats()

            stats_text = f"""
    🎫 *УПРАВЛЕНИЕ ПРОМОКОДАМИ*

    *Статистика:*
    • Всего кодов: {stats['total_codes']}
    • Активных: {stats['active_codes']} 
    • Использовано: {stats['used_codes']}
    • Всего активаций: {stats['total_uses']}

    *Команды:*
    /create_promo - создать промокоды
    /list_promos - список кодов
    /promo_stats - статистика
            """

            await update.message.reply_text(
                stats_text,
                parse_mode='Markdown',
                reply_markup=self.get_promo_management_keyboard()
            )
        except Exception as e:
            # Если возникает ошибка с Markdown, отправляем простой текст
            logger.error(f"❌ Ошибка отправки сообщения: {e}")
            simple_text = f"""
    🎫 УПРАВЛЕНИЕ ПРОМОКОДАМИ

    Статистика:
    • Всего кодов: {stats.get('total_codes', 0)}
    • Активных: {stats.get('active_codes', 0)}
    • Использовано: {stats.get('used_codes', 0)}
    • Всего активаций: {stats.get('total_uses', 0)}

    Команды:
    /create_promo - создать промокоды
    /list_promos - список кодов
    /promo_stats - статистика
            """

            await update.message.reply_text(
                simple_text,
                reply_markup=self.get_promo_management_keyboard()
            )

    async def users_search_menu(self, update: Update, context):
        """Меню поиска пользователей"""
        user = update.effective_user

        if not self.is_admin(user.id):
            await update.message.reply_text("❌ У вас нет доступа")
            return

        context.user_data['awaiting_user_search'] = True
        await update.message.reply_text(
            "🔍 *ПОИСК ПОЛЬЗОВАТЕЛЕЙ*\n\n"
            "Введите имя, username или Telegram ID для поиска:",
            parse_mode='Markdown'
        )

    async def send_to_user_menu(self, update: Update, context):
        """Меню отправки сообщения конкретному пользователю"""
        user = update.effective_user

        if not self.is_admin(user.id):
            await update.message.reply_text("❌ У вас нет доступа к этой команде")
            return

        await update.message.reply_text(
            "👤 *ОТПРАВКА СООБЩЕНИЯ ПОЛЬЗОВАТЕЛЮ*\n\n"
            "Введите Telegram ID пользователя:",
            parse_mode='Markdown'
        )
        context.user_data['awaiting_user_id'] = True

    async def handle_user_id_input(self, update: Update, context):
        """Обработка ввода ID пользователя"""
        user = update.effective_user
        user_input = update.message.text

        if not self.is_admin(user.id):
            await update.message.reply_text("❌ У вас нет доступа")
            return

        if not user_input.isdigit():
            await update.message.reply_text(
                "❌ *Неверный формат ID*\n\n"
                "Telegram ID должен состоять только из цифр.\n"
                "Попробуйте еще раз:",
                parse_mode='Markdown'
            )
            return

        telegram_id = int(user_input)

        # Проверяем существует ли пользователь
        user_data = self.database._make_request('users', params={'telegram_id': f'eq.{telegram_id}'})
        if not user_data or len(user_data) == 0:
            await update.message.reply_text(
                f"❌ Пользователь с ID {telegram_id} не найден.\n"
                f"Попробуйте другой ID:",
                parse_mode='Markdown'
            )
            return

        # Сохраняем ID и запрашиваем сообщение
        context.user_data['target_user_id'] = telegram_id
        context.user_data['awaiting_user_id'] = False
        context.user_data['awaiting_user_message'] = True

        target_user = user_data[0]
        await update.message.reply_text(
            f"✅ *Пользователь найден:* {target_user.get('first_name', 'No name')}\n\n"
            f"Теперь введите сообщение для отправки:",
            parse_mode='Markdown'
        )

    async def handle_user_message_input(self, update: Update, context):
        """Обработка ввода сообщения для пользователя"""
        user = update.effective_user
        message_text = update.message.text

        if not self.is_admin(user.id):
            await update.message.reply_text("❌ У вас нет доступа")
            return

        telegram_id = context.user_data.get('target_user_id')
        if not telegram_id:
            await update.message.reply_text("❌ Ошибка: ID пользователя не найден")
            return

        # Отправляем сообщение
        try:
            await context.bot.send_message(
                chat_id=telegram_id,
                text=f"📨 *СООБЩЕНИЕ ОТ АДМИНИСТРАЦИИ*\n\n{message_text}",
                parse_mode='Markdown'
            )

            # Получаем информацию о пользователе для отчета
            user_data = self.database._make_request('users', params={'telegram_id': f'eq.{telegram_id}'})
            user_name = user_data[0].get('first_name', 'Unknown') if user_data else 'Unknown'

            await update.message.reply_text(
                f"✅ *Сообщение отправлено!*\n\n"
                f"👤 *Пользователь:* {user_name}\n"
                f"🆔 *ID:* {telegram_id}\n"
                f"💬 *Сообщение:* {message_text}",
                parse_mode='Markdown',
                reply_markup=self.get_admin_keyboard()
            )

        except Exception as e:
            logger.error(f"❌ Ошибка отправки сообщения пользователю {telegram_id}: {e}")
            await update.message.reply_text(
                f"❌ *Не удалось отправить сообщение*\n\n"
                f"Пользователь с ID {telegram_id} возможно заблокировал бота.\n"
                f"Ошибка: {str(e)}",
                parse_mode='Markdown',
                reply_markup=self.get_admin_keyboard()
            )

        # Очищаем данные
        context.user_data['awaiting_user_message'] = False
        context.user_data['target_user_id'] = None

    async def list_tickets(self, update: Update, context):
        """Список тикетов для админа"""
        user = update.effective_user

        if not self.is_admin(user.id):
            await update.message.reply_text("❌ У вас нет доступа к этой команде")
            return

        tickets = self.database.get_support_tickets(status='open')

        if not tickets:
            await update.message.reply_text("📭 Нет открытых тикетов")
            return

        tickets_text = "🎫 *ОТКРЫТЫЕ ТИКЕТЫ:*\n\n"

        for ticket in tickets[:10]:  # Показываем первые 10
            tickets_text += (
                f"*#{ticket['id']}* - {ticket['user_name']}\n"
                f"💬 {ticket['message'][:50]}...\n"
                f"🕐 {ticket['created_at'][:16]}\n"
            )

            # Кнопка для ответа
            keyboard = [[InlineKeyboardButton(
                f"Ответить на #{ticket['id']}",
                callback_data=f"respond_{ticket['id']}"
            )]]

            await update.message.reply_text(
                tickets_text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

            tickets_text = ""  # Сбрасываем для следующего сообщения

    async def start_admin_response(self, update: Update, context):
        """Начало ответа на тикет"""
        query = update.callback_query
        await query.answer()

        user = update.effective_user

        if not self.is_admin(user.id):
            await query.edit_message_text("❌ У вас нет доступа")
            return

        ticket_id = int(query.data.split('_')[1])
        context.user_data['admin_ticket_id'] = ticket_id

        # Получаем информацию о тикете
        ticket_messages = self.database.get_ticket_messages(ticket_id)

        if not ticket_messages:
            await query.edit_message_text("❌ Тикет не найден")
            return

        # Показываем историю переписки
        history_text = f"🎫 *Тикет #{ticket_id}*\n\n"

        for msg in ticket_messages:
            sender = "🛡️ Админ" if msg['is_admin'] else "👤 Пользователь"
            history_text += f"{sender} ({msg['user_name']}):\n{msg['message']}\n\n"

        history_text += "\n💬 *Введите ваш ответ:*"

        await query.edit_message_text(
            history_text,
            parse_mode='Markdown'
        )

        return ADMIN_RESPONSE

    async def handle_admin_response(self, update: Update, context):
        """Обработка ответа админа"""
        user = update.effective_user
        message_text = update.message.text
        ticket_id = context.user_data.get('admin_ticket_id')

        if not ticket_id:
            await update.message.reply_text("❌ Ошибка: тикет не найден")
            return ConversationHandler.END

        # Добавляем сообщение админа
        success = self.database.add_support_message(
            ticket_id,
            user.id,
            f"Админ {user.first_name}",
            message_text,
            True
        )

        if success:
            # Отправляем ответ пользователю
            ticket_info = self.database.get_support_tickets(user_id=None)
            ticket = next((t for t in ticket_info if t['id'] == ticket_id), None)

            if ticket:
                user_info = self.database.get_user_by_id(ticket['user_id'])
                if user_info:
                    try:
                        await self.application.bot.send_message(
                            chat_id=user_info['telegram_id'],
                            text=f"🛡️ *ОТВЕТ ПОДДЕРЖКИ* \n\n{message_text}",
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        logger.error(f"❌ Не удалось отправить ответ пользователю: {e}")

            await update.message.reply_text(
                f"✅ Ответ отправлен пользователю (тикет #{ticket_id})",
                reply_markup=self.get_admin_keyboard()
            )
        else:
            await update.message.reply_text(
                "❌ Не удалось отправить ответ",
                reply_markup=self.get_admin_keyboard()
            )

        return ConversationHandler.END

    async def cancel_admin_response(self, update: Update, context):
        """Отмена ответа админа"""
        await update.message.reply_text(
            "❌ Ответ отменен",
            reply_markup=self.get_admin_keyboard()
        )
        return ConversationHandler.END

    async def admin_stats(self, update: Update, context):
        """Статистика для админа"""
        user = update.effective_user

        if not self.is_admin(user.id):
            await update.message.reply_text("❌ У вас нет доступа")
            return

        stats = self.get_admin_stats()
        stats_text = (
            f"📊 *ДЕТАЛЬНАЯ СТАТИСТИКА*\n\n"
            f"👥 *Пользователи:*\n"
            f"• Всего: {stats['total_users']}\n"
            f"• С подписками: {stats['active_subscriptions']}\n\n"
            f"🔮 *Предсказания:*\n"
            f"• Всего: {stats['total_predictions']}\n\n"
            f"🎫 *Поддержка:*\n"
            f"• Открытых тикетов: {stats['open_tickets']}\n"
        )

        await update.message.reply_text(stats_text, parse_mode='Markdown')

    # МЕТОДЫ ДЛЯ РАБОТЫ С ПОЛЬЗОВАТЕЛЯМИ
    async def users_list(self, update: Update, context):
        """Список пользователей с пагинацией"""
        user = update.effective_user

        if not self.is_admin(user.id):
            await update.message.reply_text("❌ У вас нет доступа")
            return

        # Получаем номер страницы из callback или аргументов
        page = 1
        if update.callback_query:
            page = int(update.callback_query.data.split('_')[-1])
        elif context.args:
            try:
                page = int(context.args[0])
            except:
                page = 1

        limit = 10
        offset = (page - 1) * limit

        users = self.database.get_all_users(limit=limit, offset=offset)
        total_users = self.database.get_users_count()

        if not users:
            text = "📭 Пользователи не найдены"
            if update.callback_query:
                await update.callback_query.edit_message_text(text)
            else:
                await update.message.reply_text(text)
            return

        text = f"📋 *СПИСОК ПОЛЬЗОВАТЕЛЕЙ* (страница {page})\n\n"

        for i, user_data in enumerate(users, 1):
            user_num = offset + i
            status = "💎" if self.database._is_subscription_active(user_data) else "🆓"
            predictions = user_data.get('predictions_count', 0)

            text += (
                f"*{user_num}. {user_data.get('first_name', 'No name')}* {status}\n"
                f"   🆔: {user_data.get('telegram_id', 'N/A')}\n"
                f"   📊: {predictions} предсказаний\n"
                f"   📅: {user_data.get('created_at', '')[:10]}\n"
            )

            if i < len(users):  # Добавляем разделитель кроме последней записи
                text += "   ───────────────\n"

        text += f"\n📊 Всего пользователей: {total_users}"

        # Создаем клавиатуру пагинации
        keyboard = []
        if page > 1:
            keyboard.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"users_list_{page - 1}"))

        if len(users) == limit:  # Есть еще пользователи
            keyboard.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"users_list_{page + 1}"))

        if keyboard:
            keyboard = [keyboard]

        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_users")])

        if update.callback_query:
            await update.callback_query.edit_message_text(
                text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.message.reply_text(
                text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    async def users_search(self, update: Update, context):
        """Поиск пользователей"""
        user = update.effective_user

        if not self.is_admin(user.id):
            await update.message.reply_text("❌ У вас нет доступа")
            return

        if not context.args:
            await self.users_search_menu(update, context)
            return

        query = ' '.join(context.args)
        await self._perform_users_search(update, context, query)

    async def _perform_users_search(self, update: Update, context, query: str):
        """Выполнить поиск пользователей"""
        users = self.database.search_users(query)

        if not users:
            text = f"🔍 *Результаты поиска: '{query}'*\n\nПользователи не найдены."
            if update.callback_query:
                await update.callback_query.edit_message_text(text, parse_mode='Markdown')
            else:
                await update.message.reply_text(text, parse_mode='Markdown')
            return

        text = f"🔍 *Результаты поиска: '{query}'*\n\n"

        for i, user_data in enumerate(users[:10], 1):  # Ограничиваем 10 результатами
            status = "💎" if self.database._is_subscription_active(user_data) else "🆓"
            username = f"@{user_data.get('username')}" if user_data.get('username') else "нет username"
            predictions = user_data.get('predictions_count', 0)

            text += (
                f"*{i}. {user_data.get('first_name', 'No name')}* {status}\n"
                f"   👤: {username}\n"
                f"   🆔: {user_data.get('telegram_id', 'N/A')}\n"
                f"   📊: {predictions} предсказаний\n"
                f"   💰: {user_data.get('total_spent', 0)}₽\n"
            )

            if i < min(len(users), 10):
                text += "   ───────────────\n"

        if len(users) > 10:
            text += f"\n⚠️ Показано 10 из {len(users)} результатов"

        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_users")]]

        if update.callback_query:
            await update.callback_query.edit_message_text(
                text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.message.reply_text(
                text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    async def users_premium(self, update: Update, context):
        """Список премиум пользователей"""
        user = update.effective_user

        if not self.is_admin(user.id):
            await update.message.reply_text("❌ У вас нет доступа")
            return

        premium_users = self.database.get_users_with_subscription()

        if not premium_users:
            text = "💎 *ПРЕМИУМ ПОЛЬЗОВАТЕЛИ*\n\nПремиум пользователи не найдены."
            if update.callback_query:
                await update.callback_query.edit_message_text(text, parse_mode='Markdown')
            else:
                await update.message.reply_text(text, parse_mode='Markdown')
            return

        text = "💎 *ПРЕМИУМ ПОЛЬЗОВАТЕЛИ*\n\n"

        for i, user_data in enumerate(premium_users[:15], 1):  # Ограничиваем 15 результатами
            subscription_end = user_data.get('subscription_end', '')
            end_date = subscription_end[:10] if subscription_end else 'неизвестно'
            predictions = user_data.get('predictions_count', 0)

            text += (
                f"*{i}. {user_data.get('first_name', 'No name')}*\n"
                f"   🆔: {user_data.get('telegram_id', 'N/A')}\n"
                f"   📊: {predictions} предсказаний\n"
                f"   📅: до {end_date}\n"
            )

            if i < min(len(premium_users), 15):
                text += "   ───────────────\n"

        text += f"\n💎 Всего премиум пользователей: {len(premium_users)}"

        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_users")]]

        if update.callback_query:
            await update.callback_query.edit_message_text(
                text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.message.reply_text(
                text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    async def users_stats(self, update: Update, context):
        """Статистика пользователей"""
        user = update.effective_user

        if not self.is_admin(user.id):
            await update.message.reply_text("❌ У вас нет доступа")
            return

        all_users = self.database.get_all_users(limit=1000)  # Получаем всех для статистики
        premium_users = self.database.get_users_with_subscription()

        total_users = len(all_users)
        premium_count = len(premium_users)
        free_count = total_users - premium_count

        # Статистика по предсказаниям
        total_predictions = sum(user.get('predictions_count', 0) for user in all_users)
        avg_predictions = total_predictions / total_users if total_users > 0 else 0

        # Статистика по доходам
        total_income = sum(user.get('total_spent', 0) for user in all_users)
        avg_income = total_income / premium_count if premium_count > 0 else 0

        text = (
            f"📊 *СТАТИСТИКА ПОЛЬЗОВАТЕЛЕЙ*\n\n"
            f"👥 *Общая статистика:*\n"
            f"• Всего пользователей: {total_users}\n"
            f"• Премиум: {premium_count}\n"
            f"• Бесплатных: {free_count}\n"
            f"• Конверсия в премиум: {premium_count / total_users * 100:.1f}%\n\n"

            f"🔮 *Предсказания:*\n"
            f"• Всего предсказаний: {total_predictions}\n"
            f"• В среднем на пользователя: {avg_predictions:.1f}\n\n"

            f"💰 *Финансы:*\n"
            f"• Общий доход: {total_income}₽\n"
            f"• Средний чек: {avg_income:.0f}₽\n"
            f"• MRR: {premium_count * 199}₽\n"
        )

        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_users")]]

        if update.callback_query:
            await update.callback_query.edit_message_text(
                text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.message.reply_text(
                text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    # МЕТОДЫ ДЛЯ РАССЫЛКИ
    async def broadcast_message(self, update: Update, context):
        """Рассылка сообщения всем пользователям"""
        user = update.effective_user

        if not self.is_admin(user.id):
            await update.message.reply_text("❌ У вас нет доступа к этой команде")
            return

        if not context.args:
            await self.broadcast_menu(update, context)
            return

        message = ' '.join(context.args)
        await self._start_broadcast(update, context, message, 'all')

    async def broadcast_premium(self, update: Update, context):
        """Рассылка только премиум пользователям"""
        user = update.effective_user

        if not self.is_admin(user.id):
            await update.message.reply_text("❌ У вас нет доступа")
            return

        if not context.args:
            await update.message.reply_text("❌ Укажите сообщение для рассылки")
            return

        message = ' '.join(context.args)
        await self._start_broadcast(update, context, message, 'premium')

    async def broadcast_free(self, update: Update, context):
        """Рассылка только бесплатным пользователям"""
        user = update.effective_user

        if not self.is_admin(user.id):
            await update.message.reply_text("❌ У вас нет доступа")
            return

        if not context.args:
            await update.message.reply_text("❌ Укажите сообщение для рассылки")
            return

        message = ' '.join(context.args)
        await self._start_broadcast(update, context, message, 'free')

    async def _start_broadcast(self, update: Update, context, message: str, target: str):
        """Запуск рассылки"""
        # Подтверждение рассылки
        keyboard = [
            [InlineKeyboardButton("✅ Начать рассылку", callback_data=f"broadcast_confirm_{target}")],
            [InlineKeyboardButton("❌ Отмена", callback_data="broadcast_cancel")]
        ]

        target_text = {
            'all': 'всем пользователям',
            'premium': 'премиум пользователям',
            'free': 'бесплатным пользователям'
        }.get(target, 'пользователям')

        confirmation_text = (
            f"📢 *ПОДТВЕРЖДЕНИЕ РАССЫЛКИ*\n\n"
            f"*Получатели:* {target_text}\n"
            f"*Сообщение:*\n{message}\n\n"
            f"ℹ️ Рассылка может занять несколько минут."
        )

        context.user_data['broadcast_data'] = {
            'message': message,
            'target': target
        }

        if update.callback_query:
            await update.callback_query.edit_message_text(
                confirmation_text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.message.reply_text(
                confirmation_text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    async def _execute_broadcast(self, update: Update, context, target: str, message: str):
        """Выполнение рассылки"""
        query = update.callback_query
        await query.answer()

        # Получаем пользователей в зависимости от цели
        if target == 'premium':
            users = self.database.get_users_with_subscription()
        elif target == 'free':
            all_users = self.database.get_all_users(limit=1000)
            premium_users = self.database.get_users_with_subscription()
            premium_ids = {u['telegram_id'] for u in premium_users}
            users = [u for u in all_users if u['telegram_id'] not in premium_ids]
        else:  # all
            users = self.database.get_all_users(limit=1000)

        total_users = len(users)
        successful = 0
        failed = 0

        # Обновляем сообщение о начале рассылки
        progress_msg = await query.edit_message_text(
            f"📢 *НАЧАЛАСЬ РАССЫЛКА*\n\n"
            f"👥 Получателей: {total_users}\n"
            f"✉️ Отправлено: 0/{total_users}\n"
            f"✅ Успешно: 0\n"
            f"❌ Ошибок: 0",
            parse_mode='Markdown'
        )

        # Выполняем рассылку
        for i, user_data in enumerate(users, 1):
            try:
                telegram_id = user_data.get('telegram_id')
                if telegram_id:
                    await context.bot.send_message(
                        chat_id=telegram_id,
                        text=message,
                        parse_mode='Markdown'
                    )
                    successful += 1
                else:
                    failed += 1
            except Exception as e:
                failed += 1
                logger.error(f"❌ Ошибка отправки пользователю {user_data.get('id')}: {e}")

            # Обновляем прогресс каждые 10 сообщений или в конце
            if i % 10 == 0 or i == total_users:
                try:
                    await progress_msg.edit_text(
                        f"📢 *РАССЫЛКА В ПРОЦЕССЕ*\n\n"
                        f"👥 Получателей: {total_users}\n"
                        f"✉️ Отправлено: {i}/{total_users}\n"
                        f"✅ Успешно: {successful}\n"
                        f"❌ Ошибок: {failed}",
                        parse_mode='Markdown'
                    )
                except:
                    pass

            # Небольшая задержка чтобы не превысить лимиты Telegram
            await asyncio.sleep(0.1)

        # Финальный отчет
        report_text = (
            f"📢 *РАССЫЛКА ЗАВЕРШЕНА*\n\n"
            f"👥 Всего получателей: {total_users}\n"
            f"✅ Успешно отправлено: {successful}\n"
            f"❌ Не удалось отправить: {failed}\n"
            f"📊 Успешных доставок: {successful / total_users * 100:.1f}%"
        )

        keyboard = [[InlineKeyboardButton("🔙 В админ панель", callback_data="admin_back")]]

        await progress_msg.edit_text(
            report_text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    def get_admin_stats(self):
        """Получает статистику для админ-панели"""
        try:
            # Получаем базовую статистику
            users = self.database.get_all_users(limit=1)
            tickets = self.database.get_support_tickets(status='open')
            predictions = self.database._make_request('predictions')

            total_users = self.database.get_users_count()
            open_tickets = len(tickets) if tickets else 0
            total_predictions = len(predictions) if predictions else 0

            # Считаем активные подписки
            active_subscriptions = 0
            all_users = self.database.get_all_users(limit=1000)
            if all_users:
                for user in all_users:
                    if self.database._is_subscription_active(user):
                        active_subscriptions += 1

            return {
                'total_users': total_users,
                'active_subscriptions': active_subscriptions,
                'open_tickets': open_tickets,
                'total_predictions': total_predictions
            }
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики: {e}")
            return {
                'total_users': "N/A",
                'active_subscriptions': "N/A",
                'open_tickets': "N/A",
                'total_predictions': "N/A"
            }

    # СУЩЕСТВУЮЩИЕ ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    def get_prediction_keyboard(self):
        keyboard = [
            [InlineKeyboardButton("📖 Расширенное обоснование", callback_data="detailed_explanation")],
            [InlineKeyboardButton("🔮 Основное меню", callback_data="main_menu")],
            [InlineKeyboardButton("👤 Профиль", callback_data="profile")],
            [InlineKeyboardButton("💎 Подписка", callback_data="subscription")]
        ]
        return InlineKeyboardMarkup(keyboard)

    def get_subscription_keyboard(self):
        keyboard = [
            [InlineKeyboardButton("💎 Месяц подписки - 199₽", callback_data="month_subscription")],
            [InlineKeyboardButton("🔑 Активировать код", callback_data="activate_code")],
            [InlineKeyboardButton("👤 Профиль", callback_data="profile")]
        ]
        return InlineKeyboardMarkup(keyboard)

    async def button_handler(self, update, context):
        """Обработчик кнопок"""
        query = update.callback_query
        await query.answer()

        user = update.effective_user

        if query.data == "detailed_explanation":
            await self.generate_detailed_explanation(query, context)
        elif query.data == "main_menu":
            await self.show_main_menu_from_callback(query, context)
        elif query.data == "new_prediction":
            await self.show_spreads_menu_from_callback(query, context)
        elif query.data == "profile":
            await self.profile(update, context)
        elif query.data == "subscription":
            await self.subscription(update, context)
        elif query.data == "month_subscription":
            await self.show_payment_options(query)
        elif query.data == "activate_code":
            await self.start_code_activation(update, context)

        # Новые обработчики для управления пользователями
        elif query.data == "admin_users":
            await self.admin_users(update, context)
        elif query.data.startswith("users_list_"):
            await self.users_list(update, context)
        elif query.data == "users_search":
            await self.users_search_menu(update, context)
        elif query.data == "users_premium":
            await self.users_premium(update, context)
        elif query.data == "users_stats":
            await self.users_stats(update, context)

        # Обработчики рассылки
        elif query.data.startswith("broadcast_confirm_"):
            target = query.data.replace("broadcast_confirm_", "")
            broadcast_data = context.user_data.get('broadcast_data', {})
            await self._execute_broadcast(update, context, target, broadcast_data.get('message', ''))
        elif query.data == "broadcast_cancel":
            await query.edit_message_text("❌ Рассылка отменена")
        elif query.data == "admin_back":
            await self.admin_panel(update, context)

        # Обработчики промокодов
        elif query.data == "admin_list_promos":
            await self.list_promos_command(update, context)
        elif query.data == "admin_create_promos":
            await self.create_promo_menu(update, context)
        elif query.data == "admin_promo_stats":
            await self.promo_stats_command(update, context)

        elif query.data.startswith("respond_"):
            # Обрабатывается в ConversationHandler
            pass

    async def show_payment_options(self, query):
        """Показать варианты оплаты"""
        from config import SUBSCRIPTION_PRICE, PAYMENT_SYSTEM

        payment_text = f"""
💎 *ПРЕМИУМ ПОДПИСКА - {SUBSCRIPTION_PRICE}₽/месяц*

*Включено:*
• Неограниченные предсказания
• Расширенные обоснования  
• Приоритетная обработку
• Поддержка
• Все типы раскладов

*Способы оплаты:*
🅿️ *{PAYMENT_SYSTEM}* - основная платежная система

*Для оплаты перейдите по ссылке ниже и напишите админу после оплаты:*
[🔗 Перейти на {PAYMENT_SYSTEM}](https://funpay.com/lots/offer?id=57882803)

*После оплаты пришлите скриншот админу для активации подписки*
        """

        await query.edit_message_text(
            payment_text,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )

    async def generate_detailed_explanation(self, query, context):
        """Генерация расширенного обоснования как отдельного предсказания"""
        user_data = context.user_data.get('last_prediction')
        user = query.from_user

        if not user_data:
            await query.edit_message_text("❌ Данные не найдены")
            return

        # Проверяем лимиты для расширенного предсказания
        db_user = self.database.get_or_create_user(user)
        if not self.database.can_user_make_prediction(db_user['telegram_id']):
            await self._show_subscription_required(query, db_user)
            return

        await query.edit_message_text("📖 *Погружаюсь в глубины символов...* 🔮\n*Анализирую кармические связи...* 🌌")

        try:
            # Генерируем совершенно новое расширенное предсказание
            explanation = await self.ai_assistant.generate_detailed_explanation(
                user_data['prediction_type'],
                user_data['name'],
                user_data['partner_name'],
                user_data['birth_date'],
                user_data['zodiac_sign'],
                user_data['cards']
            )

            # Сохраняем расширенное предсказание как отдельную запись
            self.database.save_prediction(
                db_user['telegram_id'],
                f"{user_data['prediction_type']}_detailed",  # Отмечаем как расширенное
                user_data['name'],
                user_data['partner_name'],
                user_data['birth_date'],
                user_data['zodiac_sign'],
                user_data['cards'],
                explanation
            )

            response = f"""
📖 *РАСШИРЕННОЕ ПРЕДСКАЗАНИЕ*

{explanation}

*✨ Глубокое понимание открывает новые горизонты!* 🌊
            """

            await query.edit_message_text(
                response,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔮 Новое предсказание", callback_data="new_prediction")
                ]])
            )

        except Exception as e:
            logger.error(f"❌ Ошибка глубинного анализа: {e}")
            await query.edit_message_text("❌ Энергии карт временно недоступны для глубинного анализа")

    # НОВЫЕ МЕТОДЫ ДЛЯ ПРОМОКОДОВ
    async def start_code_activation(self, update, context):
        """Начало активации промокода"""
        try:
            # Обрабатываем как callback query, так и обычное сообщение
            if hasattr(update, 'callback_query') and update.callback_query:
                query = update.callback_query
                await query.answer()
                context.user_data['awaiting_promo_code'] = True
                logger.info(f"🔑 Начало активации промокода (callback) для пользователя {update.effective_user.id}")

                await query.edit_message_text(
                    "🔑 *АКТИВАЦИЯ ПРОМОКОДА*\n\n"
                    "Введите ваш промокод:\n\n"
                    "*Пример:* TAROT2024\n\n"
                    "Для отмены введите /cancel",
                    parse_mode='Markdown'
                )
            else:
                # Это обычное сообщение
                context.user_data['awaiting_promo_code'] = True
                logger.info(f"🔑 Начало активации промокода (message) для пользователя {update.effective_user.id}")

                await update.message.reply_text(
                    "🔑 *АКТИВАЦИЯ ПРОМОКОДА*\n\n"
                    "Введите ваш промокод:\n\n"
                    "*Пример:* TAROT2024\n\n"
                    "Для отмены введите /cancel",
                    parse_mode='Markdown'
                )
        except Exception as e:
            logger.error(f"❌ Ошибка в start_code_activation: {e}")
            # Простая версия без Markdown
            simple_text = """
    🔑 АКТИВАЦИЯ ПРОМОКОДА

    Введите ваш промокод:

    Пример: TAROT2024

    Для отмены введите /cancel
            """
            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.edit_message_text(simple_text)
            else:
                await update.message.reply_text(simple_text)

    async def handle_promo_code_input(self, update, context):
        """Обработка ввода промокода"""
        user = update.effective_user
        code = update.message.text.strip().upper()

        logger.info(f"🔑 Пользователь {user.id} пытается активировать промокод: {code}")

        # Проверяем флаг более тщательно
        if not context.user_data.get('awaiting_promo_code'):
            logger.warning(f"❌ Неожиданный ввод промокода {code}. Флаг: {context.user_data.get('awaiting_promo_code')}")
            # Все равно попробуем обработать, если пользователь явно ввел промокод
            logger.info(f"🔑 Попытка обработки промокода {code} без флага")
            success = self.database.use_promo_code(code, user.id)

            if success:
                await update.message.reply_text(
                    "✅ *Промокод активирован!*\n\n"
                    "Ваша подписка успешно активирована! 🎉",
                    parse_mode='Markdown',
                    reply_markup=self.get_main_keyboard()
                )
            else:
                await update.message.reply_text(
                    "❌ *Неверный промокод или он уже использован*",
                    parse_mode='Markdown',
                    reply_markup=self.get_main_keyboard()
                )
            return

        # Сбрасываем флаг
        context.user_data['awaiting_promo_code'] = False
        logger.info(f"🔑 Флаг awaiting_promo_code сброшен")

        # Активируем промокод
        success = self.database.use_promo_code(code, user.id)

        if success:
            logger.info(f"✅ Промокод {code} успешно активирован для пользователя {user.id}")
            await update.message.reply_text(
                "✅ *Промокод активирован!*\n\n"
                "Ваша подписка успешно активирована! 🎉\n\n"
                "Теперь вы можете:\n"
                "• Делать неограниченное количество предсказаний\n"
                "• Получать расширенные обоснования\n"
                "• Использовать все типы раскладов\n\n"
                "*Проверить статус подписки:* /profile",
                parse_mode='Markdown',
                reply_markup=self.get_main_keyboard()
            )
        else:
            logger.warning(f"❌ Не удалось активировать промокод {code} для пользователя {user.id}")
            await update.message.reply_text(
                "❌ *Неверный промокод*\n\n"
                "Возможные причины:\n"
                "• Код не существует\n"
                "• Код уже использован\n"
                "• Срок действия истек\n"
                "• Достигнут лимит активаций\n\n"
                "Попробуйте другой код или воспользуйтесь обычной оплатой",
                parse_mode='Markdown',
                reply_markup=self.get_subscription_keyboard()
            )

    async def create_promo_command(self, update: Update, context):
        """Создание промокодов (админ)"""
        user = update.effective_user

        if not self.is_admin(user.id):
            await update.message.reply_text("❌ У вас нет доступа")
            return

        if not context.args:
            await update.message.reply_text(
                "📝 *Создание промокодов*\n\n"
                "Использование:\n"
                "/create_promo <кол-во> <дней> <использований>\n\n"
                "*Пример:*\n"
                "/create_promo 5 30 1 - 5 кодов на 30 дней, одноразовые\n"
                "/create_promo 1 60 10 - 1 код на 60 дней, 10 использований",
                parse_mode='Markdown'
            )
            return

        try:
            count = int(context.args[0])
            days = int(context.args[1])
            max_uses = int(context.args[2]) if len(context.args) > 2 else 1

            from promo_manager import PromoCodeManager
            promo_manager = PromoCodeManager(self.database)
            codes = promo_manager.create_promo_batch(count, days, max_uses, user.id)

            if codes:
                codes_text = "\n".join([f"• `{code}`" for code in codes])
                await update.message.reply_text(
                    f"✅ *Создано {len(codes)} промокодов*\n\n"
                    f"*Коды:*\n{codes_text}\n\n"
                    f"*Параметры:*\n"
                    f"• Дней: {days}\n"
                    f"• Использований: {max_uses}",
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text("❌ Не удалось создать промокоды")

        except (ValueError, IndexError):
            await update.message.reply_text("❌ Неверный формат команды")

    async def list_promos_command(self, update: Update, context):
        """Список промокодов (админ)"""
        user = update.effective_user

        if not self.is_admin(user.id):
            await update.message.reply_text("❌ У вас нет доступа")
            return

        promos = self.database.get_all_promo_codes()

        if not promos:
            await update.message.reply_text("📭 Промокоды не найдены")
            return

        text = "📋 *СПИСОК ПРОМОКОДОВ*\n\n"

        for promo in promos[:20]:
            status = "✅" if promo['is_active'] else "❌"
            text += (
                f"*{promo['code']}* {status}\n"
                f"• Дней: {promo['days']} | Использований: {promo['used_count']}/{promo['max_uses']}\n"
                f"• Создан: {promo['created_at'][:10]}\n"
            )

            if promo['description']:
                text += f"• Описание: {promo['description']}\n"

            text += "────────────────────\n"

        if len(promos) > 20:
            text += f"\n⚠️ Показано 20 из {len(promos)} кодов"

        await update.message.reply_text(text, parse_mode='Markdown')

    async def promo_stats_command(self, update: Update, context):
        """Статистика промокодов (админ)"""
        user = update.effective_user

        if not self.is_admin(user.id):
            await update.message.reply_text("❌ У вас нет доступа")
            return

        from promo_manager import PromoCodeManager
        promo_manager = PromoCodeManager(self.database)
        stats = promo_manager.get_promo_stats()

        stats_text = f"""
📊 *СТАТИСТИКА ПРОМОКОДОВ*

*Общая статистика:*
• Всего кодов: {stats['total_codes']}
• Активных: {stats['active_codes']}
• Использованных: {stats['used_codes']}
• Всего активаций: {stats['total_uses']}

*Эффективность:*
• Конверсия: {stats['used_codes']/stats['total_codes']*100:.1f}% кодов использованы
• В среднем использований на код: {stats['total_uses']/stats['total_codes']:.1f}
        """

        await update.message.reply_text(stats_text, parse_mode='Markdown')

    async def create_promo_menu(self, update, context):
        """Меню создания промокодов"""
        try:
            # Проверяем, это callback query или обычное сообщение
            if hasattr(update, 'callback_query') and update.callback_query:
                query = update.callback_query
                await query.answer()
                await query.edit_message_text(
                    "➕ *СОЗДАНИЕ ПРОМОКОДОВ*\n\n"
                    "Используйте команды:\n\n"
                    "📝 *Создание партии:*\n"
                    "`/create_promo 5 30 1` - 5 кодов на 30 дней, одноразовые\n\n"
                    "📋 *Просмотр кодов:*\n"
                    "`/list_promos` - список всех кодов\n\n"
                    "📊 *Статистика:*\n"
                    "`/promo_stats` - статистика использования",
                    parse_mode='Markdown'
                )
            else:
                # Это обычное сообщение
                await update.message.reply_text(
                    "➕ *СОЗДАНИЕ ПРОМОКОДОВ*\n\n"
                    "Используйте команды:\n\n"
                    "📝 *Создание партии:*\n"
                    "`/create_promo 5 30 1` - 5 кодов на 30 дней, одноразовые\n\n"
                    "📋 *Просмотр кодов:*\n"
                    "`/list_promos` - список всех кодов\n\n"
                    "📊 *Статистика:*\n"
                    "`/promo_stats` - статистика использования",
                    parse_mode='Markdown'
                )
        except Exception as e:
            logger.error(f"❌ Ошибка в create_promo_menu: {e}")
            # Простая версия без Markdown
            simple_text = """
    ➕ СОЗДАНИЕ ПРОМОКОДОВ

    Используйте команды:

    📝 Создание партии:
    /create_promo 5 30 1 - 5 кодов на 30 дней, одноразовые

    📋 Просмотр кодов:
    /list_promos - список всех кодов

    📊 Статистика:
    /promo_stats - статистика использования
            """
            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.edit_message_text(simple_text)
            else:
                await update.message.reply_text(simple_text)

    def _get_user_status_text(self, db_user):
        """Получить текстовый статус пользователя"""
        stats = self.database.get_user_stats(db_user['telegram_id'])
        if stats['has_subscription']:
            return "💎 ПРЕМИУМ"
        else:
            return "🆓 БЕСПЛАТНЫЙ"

    def _get_prediction_footer(self, db_user):
        """Получить футер для предсказания"""
        stats = self.database.get_user_stats(db_user['telegram_id'])

        if stats['has_subscription']:
            return "Пусть звезды благоволят вам! 💫"
        else:
            return f"Осталось бесплатных предсказаний: {stats['remaining_predictions']} 🎯"

    def _get_subscription_status(self, stats):
        """Получить статус подписки"""
        if stats['has_subscription']:
            return "✅ АКТИВНА"
        else:
            return "❌ НЕ АКТИВНА"

    def _get_subscription_date(self, stats):
        """Получить дату подписки"""
        if stats['subscription_end'] and stats['subscription_end'] != "неизвестно":
            return f"До: {stats['subscription_end']}"
        else:
            return "Не активирована"

    async def _show_subscription_required(self, update, db_user):
        """Показать сообщение о необходимости подписки"""
        stats = self.database.get_user_stats(db_user['telegram_id'])

        text = f"""
❌ *ЛИМИТ ПРЕДСКАЗАНИЙ ИСЧЕРПАН*

*📊 Ваша статистика:*
• Сделано предсказаний: {stats['predictions_count']}
• Бесплатный лимит: {FREE_PREDICTIONS_LIMIT}

*💎 Для продолжения нужна подписка:*
• 💎 Месяц премиума - {SUBSCRIPTION_PRICE}₽
• 🔑 Активация промокода

*✨ С подпиской вы получаете:*
• Неограниченные предсказания
• Расширенные обоснования
• Приоритетную обработку
• Все типы раскладов
        """

        if hasattr(update, 'message'):
            await update.message.reply_text(
                text,
                parse_mode='Markdown',
                reply_markup=self.get_subscription_keyboard()
            )
        else:
            await update.callback_query.edit_message_text(
                text,
                parse_mode='Markdown',
                reply_markup=self.get_subscription_keyboard()
            )