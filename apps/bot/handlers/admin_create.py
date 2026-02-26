from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from ..utils.db import (
    get_device_types, get_departments, create_employee,
    create_device_with_qr
)
from ..keyboards.inline import (
    types_keyboard, departments_keyboard, cancel_keyboard
)

router = Router()

class CreateDeviceStates(StatesGroup):
    waiting_for_confirmation = State()
    waiting_for_employee_name = State()
    waiting_for_department = State()
    waiting_for_device_name = State()
    waiting_for_inventory = State()
    waiting_for_type = State()

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

@router.message(CreateDeviceStates.waiting_for_employee_name)
async def process_employee_name(message: Message, state: FSMContext):
    full_name = message.text.strip()
    if len(full_name) < 3:
        await message.answer("Слишком короткое имя. Введите ФИО полностью:")
        return

    employee = await create_employee(full_name=full_name, is_approved=True)
    await state.update_data(responsible_id=employee.id)

    departments = await get_departments()
    if not departments:
        await message.answer("В системе нет отделов. Сначала создайте их через админку.")
        await state.clear()
        return

    await message.answer(
        "Выберите отдел, в котором находится техника:",
        reply_markup=departments_keyboard(departments, action_prefix="dept")
    )
    await state.set_state(CreateDeviceStates.waiting_for_department)

@router.callback_query(CreateDeviceStates.waiting_for_department, F.data.startswith("dept_"))
async def process_department(callback: CallbackQuery, state: FSMContext):
    dept_id = int(callback.data.split("_")[1])
    await state.update_data(department_id=dept_id)

    await callback.message.edit_text("Введите название устройства (модель):")
    await state.set_state(CreateDeviceStates.waiting_for_device_name)
    await callback.answer()

@router.message(CreateDeviceStates.waiting_for_device_name)
async def process_device_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("Слишком короткое название. Введите ещё раз:")
        return
    await state.update_data(device_name=name)
    await message.answer("Введите инвентарный номер:")
    await state.set_state(CreateDeviceStates.waiting_for_inventory)

@router.message(CreateDeviceStates.waiting_for_inventory)
async def process_inventory(message: Message, state: FSMContext):
    inv = message.text.strip()
    await state.update_data(inventory_number=inv)

    types = await get_device_types()
    if not types:
        await message.answer("В системе нет типов техники. Сначала создайте их через админку.")
        await state.clear()
        return

    await message.answer("Выберите тип техники:", reply_markup=types_keyboard(types))
    await state.set_state(CreateDeviceStates.waiting_for_type)

@router.callback_query(CreateDeviceStates.waiting_for_type, F.data.startswith("type_"))
async def process_type(callback: CallbackQuery, state: FSMContext):
    type_id = int(callback.data.split("_")[1])
    await state.update_data(device_type_id=type_id)

    await finish_creation(callback.message, state)
    await callback.answer()

async def finish_creation(event, state: FSMContext):
    data = await state.get_data()
    qr_code = data.get('qr_code')
    name = data.get('device_name')
    inv = data.get('inventory_number')
    type_id = data.get('device_type_id')
    dept_id = data.get('department_id')
    resp_id = data.get('responsible_id')

    device = await create_device_with_qr(
        code=qr_code,
        name=name,
        inventory_number=inv,
        device_type_id=type_id,
        department_id=dept_id,
        responsible_id=resp_id
    )
    await event.answer(
        f"✅ Техника успешно создана!\n"
        f"Название: {device.name}\n"
        f"Инв. №: {device.inventory_number}\n"
        f"Ответственный: {device.responsible.full_name if device.responsible else '—'}\n"
        f"QR-код: {qr_code} привязан."
    )
    await state.clear()