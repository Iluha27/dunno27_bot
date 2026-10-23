import os
import threading
from flask import Flask

# ... (остальные импорты и код бота) ...

app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Bot is running!"

def run_web():
    # Render передает порт через переменную окружения PORT
    port = int(os.environ.get("PORT", 10000)) # 10000 - дефолтный порт Render
    app_web.run(host="0.0.0.0", port=port) # Обязательно host="0.0.0.0"

if __name__ == "__main__":
    # Запускаем веб-сервер в отдельном потоке, чтобы он не блокировал бота
    threading.Thread(target=run_web).start()
    main() # Запускаем самого бота
import sys
from datetime import datetime
import requests
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import os
from flask import Flask

app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Bot is running!"
# ========== ВАШИ КЛЮЧИ ==========
BOT_TOKEN = os.environ.get("BOT_TOKEN")
YANDEX_API_KEY = os.environ.get("YANDEX_API_KEY")
# ================================

def get_schedule(from_city: str, to_city: str, date_str: str) -> str:
    """Запрашивает расписание, передавая названия городов напрямую (без кодов)."""
    url = f"https://api.rasp.yandex-net.ru/v3.0/search/?apikey={YANDEX_API_KEY}&from={from_city}&to={to_city}&lang=ru_RU&date={date_str}&transport_types=train"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            segments = data.get('segments')
            if not segments:
                return f"🚫 На {date_str} поездов не найдено."
            header = f"🚉 *{from_city} → {to_city}* на {date_str}\n\n"
            lines = []
            for i, seg in enumerate(segments[:5], 1):
                train = seg.get('thread', {}).get('number', '?')
                dep_raw = seg.get('departure', '??:??')
                arr_raw = seg.get('arrival', '??:??')
                dep = dep_raw.split('T')[1][:5] if 'T' in dep_raw else dep_raw
                arr = arr_raw.split('T')[1][:5] if 'T' in arr_raw else arr_raw
                lines.append(f"{i}. 🚄 *Поезд №{train}*\n   🕒 {dep} → {arr}")
            return header + "\n\n".join(lines)
        else:
            return f"❌ Ошибка API: {resp.status_code}"
    except Exception as e:
        return f"❌ Ошибка: {e}"

def get_main_keyboard():
    buttons = [
        [KeyboardButton("🚂 Расписание поездов")],
        [KeyboardButton("❓ Помощь")]
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚆 Привет! Я бот расписания поездов.\n\n"
        "📌 *Как использовать:*\n"
        "• Напиши `Город в Город` (сегодня)\n"
        "• Или `Город в Город ГГГГ-ММ-ДД`\n"
        "• Пример: `Москва в Санкт-Петербург`\n\n"
        "Я понимаю русские названия городов, коды не нужны.",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Формат:\n"
        "`Москва в Санкт-Петербург` – сегодня\n"
        "`Москва в Санкт-Петербург 2026-05-10` – конкретная дата\n\n"
        "Пишите города на русском, бот сам их найдёт.",
        parse_mode="Markdown"
    )

async def trains_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Введите маршрут в формате:\n"
        "`Город в Город` или `Город в Город ГГГГ-ММ-ДД`\n"
        "Пример: `Москва в Санкт-Петербург`",
        parse_mode="Markdown"
    )

async def help_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await help_command(update, context)

async def text_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if " в " not in text:
        return
    parts = text.split(" в ")
    if len(parts) != 2:
        await update.message.reply_text("Неверный формат. Пример: `Москва в Санкт-Петербург`", parse_mode="Markdown")
        return
    from_city = parts[0].strip()
    rest = parts[1].strip().split()
    to_city = rest[0]
    date_str = rest[1] if len(rest) > 1 else datetime.now().strftime("%Y-%m-%d")
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        await update.message.reply_text("Дата должна быть в формате ГГГГ-ММ-ДД, например 2026-05-10")
        return
    msg = await update.message.reply_text(f"🔍 Ищу поезда из *{from_city}* в *{to_city}* на {date_str}...", parse_mode="Markdown")
    result = get_schedule(from_city, to_city, date_str)
    await msg.edit_text(result, parse_mode="Markdown")

def main():
    logging.basicConfig(level=logging.WARNING)
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.Regex("^🚂 Расписание поездов$"), trains_button))
    app.add_handler(MessageHandler(filters.Regex("^❓ Помощь$"), help_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_schedule))
    app.run_polling()

def run_web():
    # Render сам выдаст нужный порт через переменную PORT
    import os
    port = int(os.environ.get("PORT", 8080))
    app_web.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    # Запускаем веб-сервер в отдельном потоке
    threading.Thread(target=run_web).start()
    # Запускаем самого бота
    main()
