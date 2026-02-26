import math
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from ..utils.db import get_employee_by_telegram, get_employee_devices
from ..keyboards.inline import devices_list_keyboard, device_detail_keyboard

router = Router()

ITEMS_PER_PAGE = 5

@router.message(Command("my"))
async def cmd_my_devices(message: Message):
    """Обработка команды /my"""
    employee = await get_employee_by_telegram(message.from_user.id)
    if not employee:
        await message.answer("❌ Вы не зарегистрированы. Используйте /start")
        return
    devices = await get_employee_devices(employee)
    if not devices:
        await message.answer("У вас нет закреплённой техники.")
        return
    await show_devices_page(message, devices, page=1)

@router.callback_query(F.data == "my_devices")
async def callback_my_devices(callback: CallbackQuery):
    """Обработка нажатия на inline-кнопку 'Моя техника'"""
    await callback.answer()
    employee = await get_employee_by_telegram(callback.from_user.id)
    if not employee:
        await callback.message.answer("❌ Вы не зарегистрированы. Используйте /start")
        return
    devices = await get_employee_devices(employee)
    if not devices:
        await callback.message.answer("У вас нет закреплённой техники.")
        return
    await show_devices_page(callback, devices, page=1)

async def show_devices_page(event, devices, page):
    """Отображает страницу со списком устройств"""
    total_pages = math.ceil(len(devices) / ITEMS_PER_PAGE)
    start = (page - 1) * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    page_devices = devices[start:end]

    text = f"📋 Ваша техника (страница {page}/{total_pages}):\n\n"
    for d in page_devices:
        text += f"🔹 {d.inventory_number} – {d.name}\n"

    kb = devices_list_keyboard(page_devices, page, total_pages, action_prefix="my_device_detail")
    if isinstance(event, Message):
        await event.answer(text, reply_markup=kb)
    elif isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=kb)

@router.callback_query(F.data.startswith("my_page_"))
async def paginate_my_devices(callback: CallbackQuery):
    """Пагинация в списке устройств"""
    page = int(callback.data.split("_")[-1])
    employee = await get_employee_by_telegram(callback.from_user.id)
    devices = await get_employee_devices(employee)
    await show_devices_page(callback, devices, page)
    await callback.answer()

@router.callback_query(F.data.startswith("my_device_detail_"))
async def device_detail(callback: CallbackQuery):
    """Детальная информация об устройстве"""
    device_id = int(callback.data.split("_")[-1])
    from apps.core.models import Device
    from asgiref.sync import sync_to_async
    get_device = sync_to_async(Device.objects.select_related('responsible', 'department', 'device_type').get)
    device = await get_device(id=device_id)

    text = (
        f"🔹 <b>{device.name}</b>\n"
        f"📌 Инв. номер: {device.inventory_number}\n"
        f"🏷 Тип: {device.device_type.name}\n"
        f"🏢 Отдел: {device.department.name if device.department else '—'}\n"
        f"👤 Ответственный: {device.responsible.full_name if device.responsible else '—'}\n"
        f"⚙️ Статус: {'✅ В эксплуатации' if device.status else '❌ Не в эксплуатации'}\n"
        f"🔢 Серийный №: {device.serial_number or '—'}"
    )

    is_owner = device.responsible and device.responsible.telegram_id == callback.from_user.id
    await callback.message.edit_text(text, reply_markup=device_detail_keyboard(device.id, is_owner))
    await callback.answer()