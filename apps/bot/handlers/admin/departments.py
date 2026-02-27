from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from asgiref.sync import sync_to_async
from apps.core.models import AdminScope
from aiogram.exceptions import TelegramBadRequest

from ...utils.db import is_admin, get_all_departments, get_employees_by_department
from ...keyboards.inline import departments_keyboard, employees_by_department_keyboard, confirm_keyboard, cancel_keyboard
from .common import back_to_main_menu, AddDepartmentStates, send_long_message

router = Router()

@sync_to_async
def get_department_by_id(dept_id):
    from apps.core.models import Department
    try:
        return Department.objects.get(id=dept_id)
    except Department.DoesNotExist:
        return None

@sync_to_async
def create_department(name, description, admin_telegram_id):
    from apps.core.models import Department, Employee
    admin_emp = Employee.objects.filter(telegram_id=admin_telegram_id, is_admin=True, is_approved=True).first()
    region = None
    if admin_emp:
        scope = AdminScope.objects.filter(employee=admin_emp).prefetch_related('allowed_regions').first()
        if scope and not scope.can_manage_all_regions:
            region = scope.allowed_regions.first()
    return Department.objects.create(name=name, description=description, region=region)

@sync_to_async
def department_exists(name):
    from apps.core.models import Department
    return Department.objects.filter(name=name).exists()

@router.callback_query(F.data == "admin_departments_menu")
async def departments_menu(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    depts = await get_all_departments(callback.from_user.id)
    kb = departments_keyboard(depts, action_prefix="dept")
    await callback.message.edit_text("🏢 Выберите отдел:", reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.regexp(r"^dept_\d+$"))
async def show_department_employees(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    dept_id = int(callback.data.split("_")[-1])
    employees = await get_employees_by_department(dept_id, callback.from_user.id)
    if not employees:
        await callback.message.edit_text("В этом отделе нет сотрудников.")
        await callback.answer()
        return
    kb = employees_by_department_keyboard(employees, dept_id, page=1)
    try:
        await callback.message.edit_text(
            f"Сотрудники отдела:\n(нажмите на имя для редактирования)",
            reply_markup=kb
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await callback.answer()
        else:
            raise e
    await callback.answer()

@router.callback_query(F.data.startswith("dept_emps_page_"))
async def paginate_employees(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    parts = callback.data.split("_")
    dept_id = int(parts[3])
    page = int(parts[4])
    employees = await get_employees_by_department(dept_id, callback.from_user.id)
    kb = employees_by_department_keyboard(employees, dept_id, page=page)
    try:
        await callback.message.edit_reply_markup(reply_markup=kb)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            pass
        else:
            raise e
    await callback.answer()

@router.callback_query(F.data == "admin_add_department")
async def add_department_start(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    await callback.message.edit_text("Введите название нового отдела:", reply_markup=cancel_keyboard())
    await state.set_state(AddDepartmentStates.waiting_for_name)
    await callback.answer()

@router.message(AddDepartmentStates.waiting_for_name)
async def process_dept_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("Слишком короткое название.")
        return
    await state.update_data(name=name)
    await message.answer("Введите описание отдела (можно пропустить, отправив '—'):")
    await state.set_state(AddDepartmentStates.waiting_for_description)

@router.message(AddDepartmentStates.waiting_for_description)
async def process_dept_description(message: Message, state: FSMContext):
    desc = message.text.strip()
    if desc == '—':
        desc = ''
    await state.update_data(description=desc)
    data = await state.get_data()
    await message.answer(
        f"Подтвердите создание отдела:\nНазвание: {data['name']}\nОписание: {data['description'] or '—'}\n\nВсё верно?",
        reply_markup=confirm_keyboard("adddept_yes", "adddept_no")
    )
    await state.set_state(AddDepartmentStates.confirmation)

@router.callback_query(AddDepartmentStates.confirmation, F.data == "adddept_yes")
async def confirm_create_dept(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    name = data['name']
    desc = data['description']
    exists = await department_exists(name)
    if exists:
        await callback.message.edit_text(f"❌ Отдел с названием «{name}» уже существует.")
        await state.clear()
        await back_to_main_menu(callback, callback.from_user.id)
        return
    await create_department(name, desc, callback.from_user.id)
    await callback.message.edit_text(f"✅ Отдел «{name}» создан.")
    await state.clear()
    await back_to_main_menu(callback, callback.from_user.id)

@router.callback_query(AddDepartmentStates.confirmation, F.data == "adddept_no")
async def cancel_create_dept(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("❌ Создание отменено.")
    await state.clear()
    await back_to_main_menu(callback, callback.from_user.id)