import logging
import sys
from datetime import datetime
import aiohttp
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor

load_dotenv('/storage/emulated/0/MyBots/.env')
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")

if not BOT_TOKEN or not YANDEX_API_KEY:
    raise ValueError("❌ Проверьте .env: TELEGRAM_TOKEN и YANDEX_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

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

def get_main_keyboard():
    buttons = [
        [KeyboardButton("🌤 Погода"), KeyboardButton("📍 Погода рядом")],
        [KeyboardButton("💵 Курс валют"), KeyboardButton("🕒 Время")],
        [KeyboardButton("❓ Помощь"), KeyboardButton("🚂 Расписание поездов")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

async def get_schedule(from_city, to_city, date_str):
    from_code = get_city_code(from_city)
    to_code = get_city_code(to_city)
    if not from_code or not to_code:
        return f"❌ Город не найден: {from_city if not from_code else to_city}"
    url = f"https://api.rasp.yandex-net.ru/v3.0/search/?apikey={YANDEX_API_KEY}&from={from_code}&to={to_code}&lang=ru_RU&date={date_str}&transport_types=train"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    segments = data.get('segments')
                    if not segments:
                        return f"🚫 На {date_str} поездов не найдено."
                    # Красивое форматирование с отступами
                    header = f"🚉 *Маршрут:* {from_city} → {to_city}\n📅 *Дата:* {date_str}\n\n"
                    lines = []
                    for i, seg in enumerate(segments[:5], 1):
                        train = seg.get('thread', {}).get('number', '?')
                        dep_raw = seg.get('departure', '??:??')
                        arr_raw = seg.get('arrival', '??:??')
                        dep = dep_raw.split('T')[1][:5] if 'T' in dep_raw else dep_raw
                        arr = arr_raw.split('T')[1][:5] if 'T' in arr_raw else arr_raw
                        lines.append(
                            f"{i}. 🚄 *Поезд №{train}*\n"
                            f"   🕒 *Отправление:* {dep}\n"
                            f"   🏁 *Прибытие:* {arr}\n"
                        )
                    # Добавляем пустую строку между поездами
                    return header + "\n".join(lines)
                else:
                    return f"❌ Ошибка API: статус {resp.status}"
    except Exception as e:
        return f"❌ Ошибка: {e}"

@dp.message_handler(commands=['start', 'menu'])
async def start_menu(msg: types.Message):
    await msg.reply(
        "🚆 Привет! Я бот расписания поездов.\n\n"
        "📌 *Как использовать:*\n"
        "• Напиши `Город в Город` (сегодня)\n"
        "• Или `Город в Город ГГГГ-ММ-ДД`\n"
        "• Пример: `Москва в Санкт-Петербург 2026-05-10`\n\n"
        "Доступны города: Москва, СПб, Новосибирск, Екатеринбург, Казань и др.",
        parse_mode="Markdown", reply_markup=get_main_keyboard()
    )

@dp.message_handler(commands=['schedule'])
async def cmd_schedule(msg: types.Message):
    args = msg.get_args()
    if not args:
        await msg.reply("Формат: `/schedule Город в Город ГГГГ-ММ-ДД`\nПример: `/schedule Москва в СПб 2026-05-10`", parse_mode="Markdown")
        return
    parts = args.split()
    if "в" not in parts:
        await msg.reply("Не хватает 'в'")
        return
    idx = parts.index("в")
    from_city = " ".join(parts[:idx])
    rest = parts[idx+1:]
    if len(rest) < 2:
        await msg.reply("Укажите город назначения и дату")
        return
    to_city = rest[0]
    date_str = rest[1] if len(rest) > 1 else datetime.now().strftime("%Y-%m-%d")
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except:
        await msg.reply("Дата должна быть в формате ГГГГ-ММ-ДД, например 2026-05-10")
        return
    wait_msg = await msg.reply(f"🔍 Ищу поезда из *{from_city}* в *{to_city}* на {date_str}...", parse_mode="Markdown")
    result = await get_schedule(from_city, to_city, date_str)
    await wait_msg.edit_text(result, parse_mode="Markdown")

@dp.message_handler(lambda m: " в " in m.text and not m.text.startswith('/'))
async def text_schedule(msg: types.Message):
    parts = msg.text.split(" в ")
    if len(parts) != 2:
        await msg.reply("Формат: `Город в Город` или `Город в Город ГГГГ-ММ-ДД`\nПример: `Москва в Санкт-Петербург 2026-05-10`", parse_mode="Markdown")
        return
    from_city = parts[0].strip()
    rest = parts[1].strip().split()
    to_city = rest[0]
    date_str = rest[1] if len(rest) > 1 else datetime.now().strftime("%Y-%m-%d")
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except:
        await msg.reply("Неверный формат даты. Используйте ГГГГ-ММ-ДД")
        return
    wait_msg = await msg.reply(f"🔍 Ищу поезда из *{from_city}* в *{to_city}* на {date_str}...", parse_mode="Markdown")
    result = await get_schedule(from_city, to_city, date_str)
    await wait_msg.edit_text(result, parse_mode="Markdown")

# Заглушки для остальных кнопок
@dp.message_handler(lambda m: m.text == "🌤 Погода")
async def weather(m: types.Message):
    await m.reply("🌤 Функция погоды в разработке.")

@dp.message_handler(lambda m: m.text == "📍 Погода рядом")
async def weather_loc(m: types.Message):
    await m.reply("📍 Функция погоды по геолокации в разработке.")

@dp.message_handler(lambda m: m.text == "💵 Курс валют")
async def currency(m: types.Message):
    await m.reply("💵 *Курс валют:* 1 USD ≈ 95 RUB (примерно)", parse_mode="Markdown")

@dp.message_handler(lambda m: m.text == "🕒 Время")
async def time_now(m: types.Message):
    await m.reply(f"🕒 *Текущее время:* {datetime.now().strftime('%H:%M:%S')}", parse_mode="Markdown")

@dp.message_handler(lambda m: m.text == "❓ Помощь")
async def help_text(m: types.Message):
    await m.reply(
        "📌 *Как получить расписание:*\n"
        "• Просто напиши `Город в Город`\n"
        "• Или добавь дату: `Город в Город ГГГГ-ММ-ДД`\n\n"
        "🔹 *Примеры:*\n"
        "`Москва в Санкт-Петербург`\n"
        "`СПб в Москва 2026-05-15`\n\n"
        "🌍 *Доступные города:*\n"
        "Москва, СПб, Новосибирск, Екатеринбург, Казань, Нижний Новгород, Самара, Челябинск, Ростов-на-Дону, Уфа, Волгоград, Пермь, Краснодар, Сургут, Тюмень",
        parse_mode="Markdown"
    )

@dp.message_handler()
async def fallback(m: types.Message):
    await m.reply(
        "Я не понял команду.\n"
        "Используй /start или напиши маршрут в формате:\n"
        "`Город в Город` или `Город в Город ГГГГ-ММ-ДД`",
        parse_mode="Markdown"
    )

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    executor.start_polling(dp, skip_updates=True)
