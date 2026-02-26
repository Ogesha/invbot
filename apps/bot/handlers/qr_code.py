from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from ..utils.db import get_device_by_code_or_id, get_employee_by_telegram, is_admin
from ..keyboards.inline import device_detail_keyboard, confirm_keyboard
from .admin_create import CreateDeviceStates

router = Router()


def get_status_text(status_code):
    status_map = {
        'in_use': '✅ В эксплуатации',
        'not_in_use': '❌ Не в эксплуатации',
        'reserve': '🔸 Резерв',
    }
    return status_map.get(status_code, '❓ Неизвестно')


@router.message(F.text)
async def handle_qr_code(message: Message, state: FSMContext):
    code = message.text.strip()
    device = await get_device_by_code_or_id(code)

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
        else:
            text = (
                f"ℹ️ <b>{device.name}</b>\n"
                f"Инв. номер: {device.inventory_number}\n"
                f"Отдел: {device.department.name if device.department else '—'}\n"
                f"Ответственный: {device.responsible.full_name if device.responsible else '—'}\n"
                f"Статус: {get_status_text(device.status)}"
            )
        kb = device_detail_keyboard(device.id, is_owner) if is_owner else None
        await message.answer(text, reply_markup=kb)
    else:
        admin = await is_admin(message.from_user.id)
        if admin:
            await message.answer(
                f"❌ Код {code} не найден в базе.\n"
                f"Хотите создать новую технику с этим кодом?",
                reply_markup=confirm_keyboard("create_device_yes", "create_device_no")
            )
            await state.set_state(CreateDeviceStates.waiting_for_confirmation)
            await state.update_data(qr_code=code)
        else:
            await message.answer("❌ Неверный QR-код или он деактивирован.")


@router.callback_query(F.data == "create_device_yes")
async def confirm_create_device(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "Создание новой техники.\n"
        "Введите ФИО сотрудника, за которым будет закреплена техника:"
    )
    await state.set_state(CreateDeviceStates.waiting_for_employee_name)


@router.callback_query(F.data == "create_device_no")
async def cancel_create_device(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text("Создание отменено.")
    await state.clear()