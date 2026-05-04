import asyncioimport logging
import sys
from datetime import datetime
import requests
import os
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from threading import Thread
from flask import Flask

# Flask-сервер для пинга Render
web_app = Flask('')
@web_app.route('/')
def health():
    return 'OK'
def run_web():
    web_app.run(host='0.0.0.0', port=8080)
Thread(target=run_web, daemon=True).start()

# Загрузка токенов
load_dotenv()  # на Render будет искать .env в корне
BOT_TOKEN = os.getenv("BOT_TOKEN")
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
if not BOT_TOKEN or not YANDEX_API_KEY:
    raise ValueError("Отсутствуют токены в .env")

# Коды городов
CITY_CODES = {
    "москва": "c213", "санкт-петербург": "c2", "спб": "c2", "питер": "c2",
    "новосибирск": "c48", "нск": "c48", "екатеринбург": "c54", "екб": "c54",
    "казань": "c30", "нижний новгород": "c27", "самара": "c35", "омск": "c47",
    "челябинск": "c56", "ростов-на-дону": "c39", "уфа": "c36", "волгоград": "c38",
    "пермь": "c57", "краснодар": "c40", "сургут": "c973", "тюмень": "c55"
}

def get_city_code(city: str) -> str | None:
    return CITY_CODES.get(city.lower().strip())

def get_schedule_sync(from_city, to_city, date_str):
    from_code = get_city_code(from_city)
    to_code = get_city_code(to_city)
    if not from_code or not to_code:
        return f"❌ Город не найден: {from_city if not from_code else to_city}"
    url = f"https://api.rasp.yandex-net.ru/v3.0/search/?apikey={YANDEX_API_KEY}&from={from_code}&to={to_code}&lang=ru_RU&date={date_str}&transport_types=train"
    try:
        resp = requests.get(url)
        if resp.status_code == 200:
            data = resp.json()
            segments = data.get('segments')
            if not segments:
                return f"🚫 На {date_str} поездов не найдено."
            header = f"🚉 *Маршрут:* {from_city} → {to_city}\n📅 *Дата:* {date_str}\n\n"
            lines = []
            for i, seg in enumerate(segments[:5], 1):
                train = seg.get('thread', {}).get('number', '?')
                dep_raw = seg.get('departure', '??:??')
                arr_raw = seg.get('arrival', '??:??')
                dep = dep_raw.split('T')[1][:5] if 'T' in dep_raw else dep_raw
                arr = arr_raw.split('T')[1][:5] if 'T' in arr_raw else arr_raw
                lines.append(f"{i}. 🚄 *Поезд №{train}*\n   🕒 Отправление: {dep}\n   🏁 Прибытие: {arr}")
            return header + "\n\n".join(lines)
        else:
            return f"❌ Ошибка API: {resp.status_code}"
    except Exception as e:
        return f"❌ Ошибка: {e}"

async def get_schedule(from_city, to_city, date_str):
    # Запускаем синхронную функцию в отдельном потоке, чтобы не блокировать бота
    return await asyncio.to_thread(get_schedule_sync, from_city, to_city, date_str)

# Клавиатура
def get_main_keyboard():
    buttons = [
        [KeyboardButton("🌤 Погода"), KeyboardButton("📍 Погода рядом")],
        [KeyboardButton("💵 Курс валют"), KeyboardButton("🕒 Время")],
        [KeyboardButton("❓ Помощь"), KeyboardButton("🚂 Расписание поездов")]
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚆 Привет! Я бот расписания поездов.\n\n"
        "📌 *Как использовать:*\n"
        "• Напиши `Город в Город` (сегодня)\n"
        "• Или `Город в Город ГГГГ-ММ-ДД`\n"
        "• Пример: `Москва в Санкт-Петербург 2026-05-10`\n\n"
        "Доступны города: Москва, СПб, Новосибирск, Екатеринбург, Казань и др.",
        parse_mode="Markdown", reply_markup=get_main_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 *Как получить расписание:*\n"
        "• Напиши `Город в Город` (сегодня)\n"
        "• Или добавь дату: `Город в Город ГГГГ-ММ-ДД`\n\n"
        "🔹 *Примеры:*\n"
        "`Москва в Санкт-Петербург`\n"
        "`СПб в Москва 2026-05-15`\n\n"
        "🌍 *Доступные города:* " + ", ".join(CITY_CODES.keys()),
        parse_mode="Markdown"
    )

async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🕒 {datetime.now().strftime('%H:%M:%S')}")

async def currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💵 Курс валют: 1 USD ≈ 95 RUB (примерно)")

async def weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🌤 Функция погоды в разработке.")

async def weather_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📍 Функция погоды по геолокации в разработке.")

async def train_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Введите маршрут в формате:\n`Город в Город`\n"
        "Например: `Москва в Санкт-Петербург`",
        parse_mode="Markdown"
    )

async def text_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if " в " not in text:
        return
    parts = text.split(" в ")
    if len(parts) != 2:
        await update.message.reply_text("Формат: `Город в Город` или `Город в Город ГГГГ-ММ-ДД`", parse_mode="Markdown")
        return
    from_city = parts[0].strip()
    rest = parts[1].strip().split()
    to_city = rest[0]
    date_str = rest[1] if len(rest) > 1 else datetime.now().strftime("%Y-%m-%d")
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except:
        await update.message.reply_text("Неверный формат даты. Используйте ГГГГ-ММ-ДД")
        return
    msg = await update.message.reply_text(f"🔍 Ищу поезда из *{from_city}* в *{to_city}* на {date_str}...", parse_mode="Markdown")
    result = await get_schedule(from_city, to_city, date_str)
    await msg.edit_text(result, parse_mode="Markdown")

def main():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("time", time_command))
    app.add_handler(MessageHandler(filters.Regex("^🚂 Расписание поездов$"), train_prompt))
    app.add_handler(MessageHandler(filters.Regex("^❓ Помощь$"), help_command))
    app.add_handler(MessageHandler(filters.Regex("^🕒 Время$"), time_command))
    app.add_handler(MessageHandler(filters.Regex("^💵 Курс валют$"), currency))
    app.add_handler(MessageHandler(filters.Regex("^🌤 Погода$"), weather))
    app.add_handler(MessageHandler(filters.Regex("^📍 Погода рядом$"), weather_location))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_schedule))
    app.run_polling()

if __name__ == "__main__":
    main()
