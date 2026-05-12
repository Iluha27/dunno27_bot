import logging
import sys
from datetime import datetime
import requests
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ========== ВАШИ КЛЮЧИ (замените на свои) ==========
BOT_TOKEN = "6180881337:AAEZgfdGhwXMD3nB6_k6l8GHi2Ujy3OvV9g"
YANDEX_API_KEY = "e6963e02-5426-4d12-8f4a-b7e7abded541"
# =====================================================

# Функция получения кода станции через suggests Яндекса (без ключа, синхронно)
def get_station_code(station_name: str) -> str | None:
    """Возвращает yandex_code для первого найденного совпадения."""
    url = f"https://suggests.rasp.yandex.net/all_suggests?format=old&part={station_name}"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data and len(data) > 0 and isinstance(data[0], dict):
                return data[0].get('yandex_code')
        return None
    except Exception:
        return None

# Функция запроса расписания
def get_schedule(from_city: str, to_city: str, date_str: str) -> str:
    from_code = get_station_code(from_city)
    to_code = get_station_code(to_city)
    if not from_code or not to_code:
        missing = from_city if not from_code else to_city
        return f"❌ Не удалось найти код станции: '{missing}'. Попробуйте уточнить название (например, 'Москва', 'Санкт-Петербург')."
    url = f"https://api.rasp.yandex-net.ru/v3.0/search/?apikey={YANDEX_API_KEY}&from={from_code}&to={to_code}&lang=ru_RU&date={date_str}&transport_types=train"
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
        "Я сам найду нужные коды станций, список городов не нужен.",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Формат:\n"
        "`Москва в Санкт-Петербург` – показать на сегодня\n"
        "`Москва в Санкт-Петербург 2026-05-10` – на конкретную дату\n\n"
        "Бот сам подбирает коды станций через API Яндекса, поэтому пишите названия как можно точнее.",
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
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.Regex("^🚂 Расписание поездов$"), trains_button))
    app.add_handler(MessageHandler(filters.Regex("^❓ Помощь$"), help_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_schedule))
    app.run_polling()

if __name__ == "__main__":
    main()
