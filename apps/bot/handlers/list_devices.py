from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from ..utils.db import is_admin, get_departments, get_device_types, get_all_devices_filtered
from ..keyboards.inline import departments_keyboard, device_types_keyboard, status_keyboard, devices_list_keyboard

router = Router()

class FilterStates(StatesGroup):
    department = State()
    device_type = State()
    status = State()

@router.message(Command("list"))
async def cmd_list_start(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав для просмотра всего списка.")
        return

    departments = await get_departments(message.from_user.id)
    await message.answer(
        "Выберите отдел для фильтрации (или 'Все отделы'):",
        reply_markup=departments_keyboard(departments, action_prefix="list_filter_dep")
    )
    await state.set_state(FilterStates.department)

@router.callback_query(FilterStates.department, F.data.startswith("list_filter_dep_"))
async def process_department(callback: CallbackQuery, state: FSMContext):
    dep_id = callback.data.split("_")[-1]
    await state.update_data(department=dep_id)

    types = await get_device_types()
    await callback.message.edit_text(
        "Выберите тип техники:",
        reply_markup=device_types_keyboard(types, action_prefix="list_filter_type")
    )
    await state.set_state(FilterStates.device_type)
    await callback.answer()

@router.callback_query(FilterStates.device_type, F.data.startswith("list_filter_type_"))
async def process_device_type(callback: CallbackQuery, state: FSMContext):
    type_id = callback.data.split("_")[-1]
    await state.update_data(device_type=type_id)

    await callback.message.edit_text(
        "Выберите статус:",
        reply_markup=status_keyboard(action_prefix="list_filter_status")
    )
    await state.set_state(FilterStates.status)
    await callback.answer()

@router.callback_query(FilterStates.status, F.data.startswith("list_filter_status_"))
async def process_status(callback: CallbackQuery, state: FSMContext):
    status_val = callback.data.split("_")[-1]  # active, inactive, all
    data = await state.get_data()
    department = data.get('department')
    device_type = data.get('device_type')

    status = None if status_val == 'all' else (status_val == 'active')

    devices = await get_all_devices_filtered(
        department_id=None if department == 'all' else int(department),
        device_type_id=None if device_type == 'all' else int(device_type),
        status=status,
        admin_telegram_id=callback.from_user.id
    )

    if not devices:
        await callback.message.edit_text("Нет устройств, соответствующих фильтрам.")
    else:
        await state.update_data(devices_list=[d.id for d in devices])
        await show_filtered_devices(callback, devices, page=1, state=state)
    await state.set_state(None)

async def show_filtered_devices(event, devices, page, state: FSMContext):
    from math import ceil
    per_page = 5
    total_pages = ceil(len(devices) / per_page)
    start = (page - 1) * per_page
    end = start + per_page
    page_devices = devices[start:end]

    text = f"🔍 Результаты (страница {page}/{total_pages}):\n\n"
    for d in page_devices:
        text += f"🔹 {d.inventory_number} – {d.name} ({d.department.name if d.department else '—'})\n"

    kb = devices_list_keyboard(page_devices, page, total_pages, action_prefix="list_device_detail")
    if isinstance(event, Message):
        await event.answer(text, reply_markup=kb)
    elif isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=kb)
    await state.update_data(current_page=page)

@router.callback_query(F.data.startswith("list_page_"))
async def paginate_filtered(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data.split("_")[-1])
    data = await state.get_data()
    device_ids = data.get('devices_list', [])
    if not device_ids:
        await callback.answer("Список пуст или устарел.")
        return

    from asgiref.sync import sync_to_async
    from apps.core.models import Device
    get_devices = sync_to_async(lambda: list(Device.objects.filter(id__in=device_ids).select_related('department')))
    devices = await get_devices()
    await show_filtered_devices(callback, devices, page, state)
    await callback.answer()