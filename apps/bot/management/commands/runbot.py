import asyncio
from django.core.management.base import BaseCommand
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from django.conf import settings
from apps.bot.handlers import register_all_handlers

class Command(BaseCommand):
    help = 'Запуск Telegram-бота для инвентаризации'

    def handle(self, *args, **options):
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        dp = Dispatcher()
        register_all_handlers(dp)

        async def main():
            await dp.start_polling(bot)

        asyncio.run(main())