from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from ...utils.db import (
    is_admin,
    get_all_devices,
    get_device_types,
    get_all_departments,
    get_all_employees_with_dept,
    create_device,
    update_device_status,
    delete_device,
    get_device_data,
)
from .common import back_to_main_menu

router = Router()
DEVICE_PAGE_SIZE = 10


class DeviceStates(StatesGroup):
    waiting_for_inventory = State()
    waiting_for_name = State()
    waiting_for_type = State()
    waiting_for_department = State()
    waiting_for_responsible = State()
    waiting_for_status = State()
    waiting_for_delete_confirm = State()


def _device_kind(device) -> str:
    type_name = (device.device_type.name if device.device_type else "").lower()
    if any(token in type_name for token in ("принтер", "printer")):
        return "printer"
    if any(token in type_name for token in ("комп", "computer", "пк", "pc")):
        return "pc"
    return "pc"


def _devices_by_kind(devices, kind: str):
    if kind == "all":
        return devices
    return [device for device in devices if _device_kind(device) == kind]


async def _render_devices_list(callback: CallbackQuery, admin_telegram_id: int, kind: str, page: int = 1):
    devices = await get_all_devices(admin_telegram_id)
    if not devices:
        await callback.message.edit_text("Техника не найдена.")
        await back_to_main_menu(callback, admin_telegram_id)
        return

    filtered = _devices_by_kind(devices, kind)
    if not filtered:
        await callback.answer("В этой вкладке пока нет техники", show_alert=True)
        filtered = []

    total_pages = max(1, (len(filtered) + DEVICE_PAGE_SIZE - 1) // DEVICE_PAGE_SIZE)
    page = max(1, min(page, total_pages))
    start = (page - 1) * DEVICE_PAGE_SIZE
    page_items = filtered[start:start + DEVICE_PAGE_SIZE]

    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text=("🟦 Компьютеры" if kind == "pc" else "Компьютеры"), callback_data="admin_devices_list_pc_1"),
        InlineKeyboardButton(text=("🟦 Принтеры" if kind == "printer" else "Принтеры"), callback_data="admin_devices_list_printer_1"),
    )
    for device in page_items:
        kb.row(
            InlineKeyboardButton(
                text=f"{device.inventory_number} — {device.name[:28]}",
                callback_data=f"dev_{device.id}_{kind}_{page}",
            )
        )

    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"admin_devices_list_{kind}_{page - 1}"))
    nav_row.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="ignore"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"admin_devices_list_{kind}_{page + 1}"))
    kb.row(*nav_row)

    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_devices_menu"))
    title = "🖨 Список принтеров" if kind == "printer" else "🖥 Список компьютеров"
    await callback.message.edit_text(f"{title}\nВыберите технику:", reply_markup=kb.as_markup())


@router.callback_query(F.data == "admin_devices_menu")
async def devices_menu(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return

    await state.clear()
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🖥 Компьютеры", callback_data="admin_devices_list_pc_1"))
    kb.row(InlineKeyboardButton(text="🖨 Принтеры", callback_data="admin_devices_list_printer_1"))
    kb.row(InlineKeyboardButton(text="➕ Добавить технику", callback_data="admin_device_add"))
    kb.row(InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main"))
    await callback.message.edit_text("🖥 Управление техникой", reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data == "admin_devices_list")
async def devices_list_default(callback: CallbackQuery):
    await _render_devices_list(callback, callback.from_user.id, kind="pc", page=1)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^admin_devices_list_(pc|printer|all)_\d+$"))
async def devices_list(callback: CallbackQuery):
    _, _, _, kind, page = callback.data.split("_")
    await _render_devices_list(callback, callback.from_user.id, kind=kind, page=int(page))
    await callback.answer()


@router.callback_query(F.data.regexp(r"^dev_\d+_(pc|printer|all)_\d+$"))
async def device_card(callback: CallbackQuery, state: FSMContext):
    _, device_id, kind, page = callback.data.split("_")
    device = await get_device_data(int(device_id), callback.from_user.id)
    if not device:
        await callback.answer("Техника не найдена или нет доступа", show_alert=True)
        return

    await state.update_data(device_id=device.id)
    text = (
        f"🖥 <b>{device.name}</b>\n"
        f"Инв. №: <code>{device.inventory_number}</code>\n"
        f"Тип: {device.device_type.name if device.device_type else '—'}\n"
        f"Отдел: {device.department.name if device.department else '—'}\n"
        f"Ответственный: {device.responsible.full_name if device.responsible else '—'}\n"
        f"Статус: {device.get_status_display()}"
    )
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🔄 Сменить статус", callback_data=f"dev_status_{device.id}"))
    kb.row(InlineKeyboardButton(text="👤 Сменить ответственного", callback_data=f"move_dev_{device.id}"))
    kb.row(InlineKeyboardButton(text="🗑 Удалить", callback_data=f"dev_del_{device.id}"))
    kb.row(InlineKeyboardButton(text="🔙 К списку", callback_data=f"admin_devices_list_{kind}_{page}"))
    await callback.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.regexp(r"^dev_\d+$"))
async def device_card_legacy(callback: CallbackQuery, state: FSMContext):
    callback.data = f"{callback.data}_pc_1"
    await device_card(callback, state)


@router.callback_query(F.data == "admin_device_add")
async def add_device_start(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.update_data(flow="create")
    await callback.message.edit_text("Введите инвентарный номер новой техники:")
    await state.set_state(DeviceStates.waiting_for_inventory)
    await callback.answer()


@router.message(DeviceStates.waiting_for_inventory)
async def add_device_inventory(message: Message, state: FSMContext):
    inventory_number = (message.text or '').strip()
    if len(inventory_number) < 2:
        await message.answer("Инвентарный номер слишком короткий.")
        return
    await state.update_data(inventory_number=inventory_number)
    await message.answer("Введите название техники:")
    await state.set_state(DeviceStates.waiting_for_name)


@router.message(DeviceStates.waiting_for_name)
async def add_device_name(message: Message, state: FSMContext):
    name = (message.text or '').strip()
    if len(name) < 2:
        await message.answer("Название слишком короткое.")
        return
    await state.update_data(name=name)

    types = await get_device_types()
    if not types:
        await message.answer("Нет типов техники. Добавьте их в Django admin.")
        await state.clear()
        return

    kb = InlineKeyboardBuilder()
    for device_type in types[:30]:
        kb.row(InlineKeyboardButton(text=device_type.name, callback_data=f"dev_type_{device_type.id}"))
    await message.answer("Выберите тип техники:", reply_markup=kb.as_markup())
    await state.set_state(DeviceStates.waiting_for_type)


@router.callback_query(DeviceStates.waiting_for_type, F.data.regexp(r"^dev_type_\d+$"))
async def add_device_type(callback: CallbackQuery, state: FSMContext):
    device_type_id = int(callback.data.split("_")[-1])
    await state.update_data(device_type_id=device_type_id)

    departments = await get_all_departments(callback.from_user.id)
    if not departments:
        await callback.message.edit_text("Нет доступных отделов. Создайте отдел в Django admin.")
        await state.clear()
        await back_to_main_menu(callback, callback.from_user.id)
        return

    kb = InlineKeyboardBuilder()
    for department in departments[:40]:
        kb.row(InlineKeyboardButton(text=department.name, callback_data=f"dev_dept_{department.id}"))
    await callback.message.edit_text("Выберите отдел:", reply_markup=kb.as_markup())
    await state.set_state(DeviceStates.waiting_for_department)
    await callback.answer()


@router.callback_query(DeviceStates.waiting_for_department, F.data.regexp(r"^dev_dept_\d+$"))
async def add_device_department(callback: CallbackQuery, state: FSMContext):
    department_id = int(callback.data.split("_")[-1])
    await state.update_data(department_id=department_id)
    employees = await get_all_employees_with_dept(callback.from_user.id, department_id=department_id)

    kb = InlineKeyboardBuilder()
    for employee in employees[:40]:
        kb.row(InlineKeyboardButton(text=employee.full_name, callback_data=f"dev_resp_{employee.id}"))
    kb.row(InlineKeyboardButton(text="Пропустить", callback_data="dev_resp_skip"))
    await callback.message.edit_text("Выберите ответственного (или пропустите):", reply_markup=kb.as_markup())
    await state.set_state(DeviceStates.waiting_for_responsible)
    await callback.answer()


@router.callback_query(DeviceStates.waiting_for_responsible, F.data == "dev_resp_skip")
async def add_device_skip_responsible(callback: CallbackQuery, state: FSMContext):
    await state.update_data(responsible_id=None)
    await ask_status(callback, state)


@router.callback_query(DeviceStates.waiting_for_responsible, F.data.regexp(r"^dev_resp_\d+$"))
async def add_device_responsible(callback: CallbackQuery, state: FSMContext):
    responsible_id = int(callback.data.split("_")[-1])
    await state.update_data(responsible_id=responsible_id)
    await ask_status(callback, state)


async def ask_status(callback: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="В эксплуатации", callback_data="dev_st_in_use"))
    kb.row(InlineKeyboardButton(text="Не в эксплуатации", callback_data="dev_st_not_in_use"))
    kb.row(InlineKeyboardButton(text="Резерв", callback_data="dev_st_reserve"))
    await callback.message.edit_text("Выберите статус техники:", reply_markup=kb.as_markup())
    await state.set_state(DeviceStates.waiting_for_status)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^dev_status_\d+$"))
async def start_change_status(callback: CallbackQuery, state: FSMContext):
    device_id = int(callback.data.split("_")[-1])
    await state.update_data(flow="status", device_id=device_id)
    await ask_status(callback, state)


@router.callback_query(DeviceStates.waiting_for_status, F.data.regexp(r"^dev_st_.+$"))
async def handle_status(callback: CallbackQuery, state: FSMContext):
    status = callback.data.replace("dev_st_", "", 1)
    data = await state.get_data()
    flow = data.get("flow")

    if flow == "status":
        ok, msg = await update_device_status(data.get("device_id"), status, callback.from_user.id)
        await callback.message.edit_text(("✅ " if ok else "❌ ") + msg)
    else:
        success, result = await create_device(
            inventory_number=data["inventory_number"],
            name=data["name"],
            device_type_id=data["device_type_id"],
            department_id=data["department_id"],
            responsible_id=data.get("responsible_id"),
            status=status,
            admin_telegram_id=callback.from_user.id,
        )
        if not success:
            await callback.message.edit_text(f"❌ Не удалось создать технику: {result}")
        else:
            await callback.message.edit_text(
                f"✅ Техника создана: {result.inventory_number} — {result.name}\n"
                "QR-код создан автоматически и доступен в Django admin."
            )

    await state.clear()
    await back_to_main_menu(callback, callback.from_user.id)


@router.callback_query(F.data.regexp(r"^dev_del_\d+$"))
async def delete_device_start(callback: CallbackQuery, state: FSMContext):
    device_id = int(callback.data.split("_")[-1])
    device = await get_device_data(device_id, callback.from_user.id)
    if not device:
        await callback.answer("Техника не найдена", show_alert=True)
        return
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="Да, удалить", callback_data=f"dev_del_yes_{device_id}"),
        InlineKeyboardButton(text="Нет", callback_data=f"dev_{device_id}"),
    )
    await callback.message.edit_text(
        f"Удалить технику {device.inventory_number} — {device.name}?",
        reply_markup=kb.as_markup(),
    )
    await state.set_state(DeviceStates.waiting_for_delete_confirm)
    await callback.answer()


@router.callback_query(DeviceStates.waiting_for_delete_confirm, F.data.regexp(r"^dev_del_yes_\d+$"))
async def delete_device_confirm(callback: CallbackQuery, state: FSMContext):
    device_id = int(callback.data.split("_")[-1])
    ok, msg = await delete_device(device_id, callback.from_user.id)
    await callback.message.edit_text(("✅ " if ok else "❌ ") + msg)
    await state.clear()
    await back_to_main_menu(callback, callback.from_user.id)
