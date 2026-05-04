import asyncio
from telegram import Bot

BOT_TOKEN = "6180881337:AAEZgfdGhwXMD3nB6_k6l8GHi2Ujy3OvV9g"  # ваш токен

async def main():
    bot = Bot(token=BOT_TOKEN)
    me = await bot.get_me()
    print(f"Бот работает: @{me.username}")

asyncio.run(main())
