import asyncio
from telegram import Bot

BOT_TOKEN =# ваш токен

async def main():
    bot = Bot(token=BOT_TOKEN)
    me = await bot.get_me()
    print(f"Бот работает: @{me.username}")

asyncio.run(main())
