from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from asgiref.sync import sync_to_async
from aiogram.exceptions import TelegramBadRequest

from ...utils.db import (
    is_admin, create_employee, get_all_departments,
    get_employees_by_department, get_employee_data_safe,
    update_employee, delete_employee, get_all_employees_data,
    get_employee_devices
)
from ...keyboards.inline import (
    departments_keyboard, employees_by_department_keyboard,
    employee_edit_keyboard, confirm_keyboard, cancel_keyboard,
    devices_list_keyboard
)
from .common import back_to_main_menu, send_long_message, AddEmployeeStates, EditEmployeeStates

router = Router()

@sync_to_async
def get_department_by_id(dept_id):
    from apps.core.models import Department
    try:
        return Department.objects.get(id=dept_id)
    except Department.DoesNotExist:
        return None

# ---------- Редактирование сотрудника ----------
@router.callback_query(F.data.startswith("emp_edit_"))
async def employee_edit_card(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    emp_id = int(callback.data.split("_")[-1])
    emp_data = await get_employee_data_safe(emp_id)
    if not emp_data:
        await callback.message.edit_text("Сотрудник не найден.")
        await callback.answer()
        return
    text = (
        f"👤 <b>{emp_data['full_name']}</b>\n"
        f"Отдел: {emp_data['department_name'] or '—'}\n"
        f"Статус: {'✅ Подтверждён' if emp_data['is_approved'] else '⏳ Ожидает'}\n"
        f"ID: {emp_data['id']}"
    )
    kb = employee_edit_keyboard(emp_id)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await callback.answer()
        else:
            raise e
    await callback.answer()

# ---------- Изменение ФИО ----------
@router.callback_query(F.data.startswith("emp_edit_name_"))
async def edit_employee_name_start(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    emp_id = int(callback.data.split("_")[-1])
    await state.update_data(emp_id=emp_id)
    await callback.message.edit_text("Введите новое ФИО сотрудника:", reply_markup=cancel_keyboard())
    await state.set_state(EditEmployeeStates.waiting_for_new_name)
    await callback.answer()

@router.message(EditEmployeeStates.waiting_for_new_name)
async def process_new_employee_name(message: Message, state: FSMContext):
    new_name = message.text.strip()
    if len(new_name) < 3:
        await message.answer("Слишком короткое имя. Введите ФИО полностью.")
        return
    data = await state.get_data()
    emp_id = data['emp_id']
    emp = await update_employee(emp_id, full_name=new_name)
    if emp:
        await message.answer(f"✅ ФИО сотрудника изменено на: {new_name}")
    else:
        await message.answer("❌ Ошибка при обновлении.")
    await state.clear()
    await back_to_main_menu(message, message.from_user.id)

# ---------- Изменение отдела ----------
@router.callback_query(F.data.startswith("emp_edit_dept_"))
async def edit_employee_dept_start(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    emp_id = int(callback.data.split("_")[-1])
    await state.update_data(emp_id=emp_id)
    depts = await get_all_departments()
    if not depts:
        await callback.message.edit_text("Нет доступных отделов.", reply_markup=cancel_keyboard())
        return
    kb = departments_keyboard(depts, action_prefix="emp_newdept")
    await callback.message.edit_text("Выберите новый отдел:", reply_markup=kb)
    await state.set_state(EditEmployeeStates.waiting_for_new_department)
    await callback.answer()

@router.callback_query(EditEmployeeStates.waiting_for_new_department, F.data.startswith("emp_newdept_"))
async def process_new_employee_dept(callback: CallbackQuery, state: FSMContext):
    dept_id = int(callback.data.split("_")[-1])
    data = await state.get_data()
    emp_id = data['emp_id']
    emp = await update_employee(emp_id, department_id=dept_id)
    if emp:
        await callback.message.edit_text("✅ Отдел сотрудника обновлён.")
    else:
        await callback.message.edit_text("❌ Ошибка при обновлении.")
    await state.clear()
    await back_to_main_menu(callback, callback.from_user.id)

# ---------- Подтверждение сотрудника ----------
@router.callback_query(F.data.startswith("emp_approve_"))
async def approve_employee(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    emp_id = int(callback.data.split("_")[-1])
    emp = await update_employee(emp_id, is_approved=True)
    if emp:
        await callback.message.edit_text(f"✅ Сотрудник {emp.full_name} подтверждён.")
    else:
        await callback.message.edit_text("❌ Ошибка при подтверждении.")
    await back_to_main_menu(callback, callback.from_user.id)

# ---------- Удаление сотрудника ----------
@router.callback_query(F.data.startswith("emp_delete_"))
async def delete_employee_confirm(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    emp_id = int(callback.data.split("_")[-1])
    emp_data = await get_employee_data_safe(emp_id)
    if not emp_data:
        await callback.message.edit_text("Сотрудник не найден.")
        return
    text = f"❓ Вы уверены, что хотите удалить сотрудника {emp_data['full_name']}?"
    kb = confirm_keyboard(f"emp_delete_yes_{emp_id}", f"emp_delete_no_{emp_id}")
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await callback.answer()
        else:
            raise e
    await callback.answer()

@router.callback_query(F.data.startswith("emp_delete_yes_"))
async def delete_employee_execute(callback: CallbackQuery):
    emp_id = int(callback.data.split("_")[-1])
    success = await delete_employee(emp_id)
    if success:
        await callback.message.edit_text("✅ Сотрудник удалён.")
    else:
        await callback.message.edit_text("❌ Ошибка при удалении.")
    await back_to_main_menu(callback, callback.from_user.id)

@router.callback_query(F.data.startswith("emp_delete_no_"))
async def delete_employee_cancel(callback: CallbackQuery):
    await callback.message.edit_text("❌ Удаление отменено.")
    await back_to_main_menu(callback, callback.from_user.id)

# ---------- Просмотр техники сотрудника ----------
@router.callback_query(F.data.startswith("emp_devices_"))
async def show_employee_devices(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    emp_id = int(callback.data.split("_")[-1])
    devices = await get_employee_devices(emp_id)
    if not devices:
        await callback.message.edit_text("У сотрудника нет закреплённой техники.")
        await callback.answer()
        return
    # Для простоты покажем список без пагинации
    lines = []
    for dev in devices:
        lines.append(f"{dev.inventory_number} – {dev.name}")
    text = "📋 Техника сотрудника:\n" + "\n".join(lines)
    # Кнопка назад к карточке сотрудника
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🔙 Назад к сотруднику", callback_data=f"emp_edit_{emp_id}"))
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()

# ---------- Возврат к списку сотрудников отдела ----------
@router.callback_query(F.data.startswith("back_to_dept_emps_"))
async def back_to_dept_employees(callback: CallbackQuery):
    emp_id = int(callback.data.split("_")[-1])
    emp_data = await get_employee_data_safe(emp_id)
    if not emp_data or not emp_data['department_name']:
        await callback.message.edit_text("Сотрудник не найден или не имеет отдела.")
        await callback.answer()
        return
    from apps.core.models import Department
    dept = await sync_to_async(Department.objects.get)(name=emp_data['department_name'])
    employees = await get_employees_by_department(dept.id)
    kb = employees_by_department_keyboard(employees, dept.id, page=1)
    try:
        await callback.message.edit_text(
            f"Сотрудники отдела:\n(нажмите на имя для редактирования)",
            reply_markup=kb
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            pass
        else:
            raise e
    await callback.answer()

# ---------- Добавление сотрудника ----------
@router.callback_query(F.data == "admin_add_employee")
async def add_employee_start(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    await callback.message.edit_text("Добавление нового сотрудника.\nВведите ФИО:", reply_markup=cancel_keyboard())
    await state.set_state(AddEmployeeStates.waiting_for_fullname)
    await callback.answer()

@router.message(AddEmployeeStates.waiting_for_fullname)
async def process_employee_fullname(message: Message, state: FSMContext):
    full_name = message.text.strip()
    if len(full_name) < 3:
        await message.answer("Слишком короткое имя. Введите ФИО полностью.")
        return
    await state.update_data(full_name=full_name)
    depts = await get_all_departments()
    if not depts:
        await message.answer("В системе нет отделов. Сначала создайте отдел через /add_department или в админке.")
        await state.clear()
        await back_to_main_menu(message, message.from_user.id)
        return
    kb = departments_keyboard(depts, action_prefix="addemp_dept")
    await message.answer("Выберите отдел для сотрудника:", reply_markup=kb)
    await state.set_state(AddEmployeeStates.waiting_for_department)

@router.callback_query(AddEmployeeStates.waiting_for_department, F.data.startswith("addemp_dept_"))
async def process_employee_department(callback: CallbackQuery, state: FSMContext):
    dept_id = int(callback.data.split("_")[-1])
    await state.update_data(department_id=dept_id)
    data = await state.get_data()
    full_name = data['full_name']
    dept = await get_department_by_id(dept_id)
    try:
        await callback.message.edit_text(
            f"Подтвердите создание сотрудника:\nФИО: {full_name}\nОтдел: {dept.name}\n\nВсё верно?",
            reply_markup=confirm_keyboard("addemp_confirm_yes", "addemp_confirm_no")
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            pass
        else:
            raise e
    await state.set_state(AddEmployeeStates.confirmation)
    await callback.answer()

@router.callback_query(AddEmployeeStates.confirmation, F.data == "addemp_confirm_yes")
async def confirm_create_employee(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    full_name = data['full_name']
    dept_id = data['department_id']
    # Создаём сотрудника сразу подтверждённым
    emp = await create_employee(full_name=full_name, department_id=dept_id, is_approved=True)
    await callback.message.edit_text(f"✅ Сотрудник {full_name} создан и подтверждён.")
    await state.clear()
    await back_to_main_menu(callback, callback.from_user.id)

@router.callback_query(AddEmployeeStates.confirmation, F.data == "addemp_confirm_no")
async def cancel_create_employee(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("❌ Создание отменено.")
    await state.clear()
    await back_to_main_menu(callback, callback.from_user.id)

# ---------- Список всех сотрудников ----------
@router.callback_query(F.data == "admin_employees_menu")
async def show_all_employees(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    employees = await get_all_employees_data()
    if not employees:
        await callback.message.edit_text("Список сотрудников пуст.")
        await back_to_main_menu(callback, callback.from_user.id)
        return
    lines = []
    for emp in employees:
        dept = emp['department__name'] if emp['department__name'] else '—'
        status = '✅' if emp['is_approved'] else '⏳'
        lines.append(f"{status} {emp['full_name']} – {dept} (ID {emp['id']})")
    text = "📋 Список всех сотрудников:\n" + "\n".join(lines)
    await callback.message.delete()
    await send_long_message(callback.message, text)
    await back_to_main_menu(callback, callback.from_user.id)
