from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ...utils.db import (
    is_admin, get_all_devices, get_all_employees_with_dept,
    change_device_responsible, get_device_data
)
from .common import back_to_main_menu, MoveDeviceStates

router = Router()


@router.callback_query(F.data == "admin_move_device_menu")
async def move_device_menu(callback: CallbackQuery, state):
    if not await is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return

    devices = await get_all_devices()
    if not devices:
        await callback.message.edit_text("Нет техники для изменения ответственного.")
        await callback.answer()
        return

    kb = InlineKeyboardBuilder()
    for device in devices[:20]:
        kb.row(InlineKeyboardButton(
            text=f"{device.inventory_number} – {device.name[:30]}",
            callback_data=f"move_dev_{device.id}"
        ))
    kb.row(InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main"))
    await callback.message.edit_text("Выберите технику для изменения ответственного:", reply_markup=kb.as_markup())
    await state.set_state(MoveDeviceStates.waiting_for_device)
    await callback.answer()


@router.callback_query(MoveDeviceStates.waiting_for_device, F.data.startswith("move_dev_"))
async def select_device_for_move(callback: CallbackQuery, state):
    device_id = int(callback.data.split("_")[-1])
    device = await get_device_data(device_id)
    if not device:
        await callback.message.edit_text("Устройство не найдено.")
        await callback.answer()
        return

    employees = await get_all_employees_with_dept()
    if not employees:
        await callback.message.edit_text("Нет сотрудников для назначения.")
        await callback.answer()
        return

    kb = InlineKeyboardBuilder()
    for emp in employees[:30]:
        dept_name = emp.department.name if emp.department else '—'
        kb.row(InlineKeyboardButton(
            text=f"{emp.full_name} ({dept_name})",
            callback_data=f"move_emp_{emp.id}"
        ))
    kb.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))

    await state.update_data(device_id=device_id)
    await callback.message.edit_text(
        f"Техника: {device.inventory_number} – {device.name}\nВыберите нового ответственного:",
        reply_markup=kb.as_markup()
    )
    await state.set_state(MoveDeviceStates.waiting_for_employee)
    await callback.answer()


@router.callback_query(MoveDeviceStates.waiting_for_employee, F.data.startswith("move_emp_"))
async def set_new_responsible(callback: CallbackQuery, state):
    employee_id = int(callback.data.split("_")[-1])
    data = await state.get_data()
    device_id = data.get('device_id')

    success, msg, movement = await change_device_responsible(device_id, employee_id)
    if success and movement:
        text = (
            "✅ Ответственный изменён.\n\n"
            f"Техника: {movement['device'].name}\n"
            f"Инвентарник: {movement['device'].inventory_number}\n"
            f"Отдел: {movement['from_department']} → {movement['to_department']}\n"
            f"Ответственный: {movement['from_responsible']} → {movement['to_responsible']}"
        )
    else:
        text = f"❌ {msg}"

    await callback.message.edit_text(text)
    await state.clear()
    await back_to_main_menu(callback, callback.from_user.id)
