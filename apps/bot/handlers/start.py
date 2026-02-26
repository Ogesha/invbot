from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext

from ..utils.db import (
    get_employee_by_telegram,
    get_device_by_code_or_id,
    is_admin
)
from ..keyboards.inline import main_menu_keyboard

router = Router()

def get_status_text(status_code):
    status_map = {
        'in_use': '✅ В эксплуатации',
        'not_in_use': '❌ Не в эксплуатации',
        'reserve': '🔸 Резерв',
    }
    return status_map.get(status_code, '❓ Неизвестно')

@router.message(Command("start"))
async def cmd_start(message: Message, command: CommandObject, state: FSMContext):
    args = command.args
    if args:
        # Если пришли с параметром (из QR-кода)
        device = await get_device_by_code_or_id(args)
        if device:
            employee = await get_employee_by_telegram(message.from_user.id)
            is_owner = employee and device.responsible and device.responsible.id == employee.id
            if is_owner:
                text = (
                    f"✅ <b>Ваше устройство</b>\n"
                    f"🔹 <b>{device.name}</b>\n"
                    f"📌 Инв. номер: {device.inventory_number}\n"
                    f"🏷 Тип: {device.device_type.name}\n"
                    f"🏢 Отдел: {device.department.name if device.department else '—'}\n"
                    f"👤 Ответственный: {device.responsible.full_name if device.responsible else '—'}\n"
                    f"⚙️ Статус: {get_status_text(device.status)}\n"
                    f"🔢 Серийный №: {device.serial_number or '—'}"
                )
                await message.answer(text)
            else:
                text = (
                    f"ℹ️ <b>{device.name}</b>\n"
                    f"Инв. номер: {device.inventory_number}\n"
                    f"Отдел: {device.department.name if device.department else '—'}\n"
                    f"Ответственный: {device.responsible.full_name if device.responsible else '—'}\n"
                    f"Статус: {get_status_text(device.status)}"
                )
                await message.answer(text)
        else:
            await message.answer("❌ Устройство с таким кодом не найдено.")

        # После ответа показываем соответствующее меню
        employee = await get_employee_by_telegram(message.from_user.id)
        if employee and employee.is_admin:
            await message.answer(
                "Выберите действие:",
                reply_markup=main_menu_keyboard(True)
            )
        else:
            await message.answer(
                "Вы можете сканировать QR-коды и получать информацию об устройствах.",
                reply_markup=main_menu_keyboard(False)
            )
        return

    # Обычный /start без параметра
    telegram_id = message.from_user.id
    employee = await get_employee_by_telegram(telegram_id)
    if employee and employee.is_admin:
        await message.answer(
            f"👋 Здравствуйте, {employee.full_name}!",
            reply_markup=main_menu_keyboard(True)
        )
    else:
        await message.answer(
            "👋 Добро пожаловать!\n\n"
            "Этот бот предназначен для инвентаризации оборудования.\n"
            "Вы можете сканировать QR-коды, наклеенные на технику, и получать информацию о ней.\n\n"
            "Просто отправьте код с QR-кода (или перейдите по ссылке) – и бот покажет данные об устройстве.",
            reply_markup=main_menu_keyboard(False)
        )

@router.callback_query(F.data == "qr_info")
async def callback_qr_info(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "📌 Для получения информации о технике просто отсканируйте QR-код камерой телефона.\n"
        "После сканирования откроется диалог с ботом, и вы увидите данные об устройстве.\n"
        "Если техника закреплена за вами, вы увидите подробные данные, иначе – общую информацию."
    )