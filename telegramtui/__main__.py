import asyncio
from telegramtui.src.ui import App
from telegramtui.src.telegramApi import client


async def main():
    await client.initialize()
    app = App()
    app.run()


if __name__ == "__main__":
    asyncio.run(main())
