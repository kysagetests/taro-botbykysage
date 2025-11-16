from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from promo_manager import PromoCodeManager
import logging

logger = logging.getLogger(__name__)


async def promo_management(update: Update, context: ContextTypes.DEFAULT_TYPE, database):
    """Управление промокодами для админа"""
    user = update.effective_user

    promo_manager = PromoCodeManager(database)
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

    keyboard = [
        [InlineKeyboardButton("📋 Список кодов", callback_data="admin_list_promos")],
        [InlineKeyboardButton("➕ Создать коды", callback_data="admin_create_promos")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_promo_stats")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]
    ]

    await update.message.reply_text(
        stats_text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def create_promo_command(update: Update, context: ContextTypes.DEFAULT_TYPE, database):
    """Создание промокодов"""
    user = update.effective_user

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

        promo_manager = PromoCodeManager(database)
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


async def list_promos_command(update: Update, context: ContextTypes.DEFAULT_TYPE, database):
    """Список промокодов"""
    promos = database.get_all_promo_codes()

    if not promos:
        await update.message.reply_text("📭 Промокоды не найдены")
        return

    text = "📋 *СПИСОК ПРОМОКОДОВ*\n\n"

    for promo in promos[:20]:  # Ограничиваем 20 кодами
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