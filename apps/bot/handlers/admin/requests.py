from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from asgiref.sync import sync_to_async

from ...utils.db import is_admin, get_all_pending_requests_data, approve_request, reject_request
from ...notifications import send_message_sync
from .common import back_to_main_menu, send_long_message

router = Router()

# ---------- Вспомогательные функции ----------
async def send_requests_list(target):
    requests = await get_all_pending_requests_data()
    if not requests:
        await target.answer("Нет ожидающих заявок.")
        return
    lines = []
    for req in requests:
        lines.append(f"ID: {req['id']} – {req['full_name']} (@{req['telegram_username']})")
    text = "📨 Ожидающие заявки:\n" + "\n".join(lines)
    await send_long_message(target, text)

# ---------- Команды ----------
@router.message(Command("list_requests"))
async def cmd_list_requests(message: Message):
    if not await is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав.")
        return
    await send_requests_list(message)

@router.message(Command("approve_request"))
async def cmd_approve_request(message: Message):
    if not await is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав.")
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Использование: /approve_request <ID заявки>")
        return
    try:
        req_id = int(args[1])
    except ValueError:
        await message.answer("ID должен быть числом.")
        return
    success, result = await approve_request(req_id)
    if success:
        await message.answer(f"✅ Заявка одобрена. Пользователю отправлено уведомление.")
        send_message_sync(result.telegram_id, f"✅ Ваша заявка одобрена! Добро пожаловать, {result.full_name}.")
    else:
        await message.answer(f"❌ Ошибка: {result}")

@router.message(Command("reject_request"))
async def cmd_reject_request(message: Message):
    if not await is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав.")
        return
    args = message.text.split(maxsplit=2)
    if len(args) < 2:
        await message.answer("Использование: /reject_request <ID заявки> [комментарий]")
        return
    try:
        req_id = int(args[1])
    except ValueError:
        await message.answer("ID должен быть числом.")
        return
    comment = args[2] if len(args) > 2 else ""
    success, result = await reject_request(req_id, comment)
    if success:
        await message.answer(f"❌ Заявка отклонена. Пользователю отправлено уведомление.")
        text = f"❌ Ваша заявка отклонена."
        if comment:
            text += f"\nКомментарий: {comment}"
        send_message_sync(result.telegram_id, text)
    else:
        await message.answer(f"❌ Ошибка: {result}")

# ---------- Callback для списка заявок (по кнопке) ----------
@router.callback_query(F.data == "admin_list_requests")
async def callback_list_requests(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    await send_requests_list(callback.message)
    await callback.answer()
    # Не удаляем сообщение, чтобы можно было вернуться