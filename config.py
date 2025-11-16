import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# OpenRouter
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "huggingfaceh4/zephyr-7b-beta:free")

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Настройки
SUBSCRIPTION_PRICE = 199
FREE_PREDICTIONS_LIMIT = 2

# Админы (Telegram ID)
ADMIN_IDS = [6923428079]  # Замените на ваш ID

# Настройки поддержки
SUPPORT_CHAT_ID = -1001234567890  # ID чата для уведомлений поддержки (опционально)

# Платежная система
PAYMENT_SYSTEM = "FunPay"