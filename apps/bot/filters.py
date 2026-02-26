from aiogram.filters import BaseFilter
from aiogram.types import Message
from .utils.db import is_admin

class AdminFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return await is_admin(message.from_user.id)