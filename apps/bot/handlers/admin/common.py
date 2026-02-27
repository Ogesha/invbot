from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from ...utils.db import is_admin
from ...keyboards.inline import main_menu_keyboard

router = Router()

# ---------- Состояния ----------
class AddEmployeeStates(StatesGroup):
    waiting_for_fullname = State()
    waiting_for_department = State()
    confirmation = State()

class AddDepartmentStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_description = State()
    confirmation = State()

class EditEmployeeStates(StatesGroup):
    waiting_for_new_name = State()
    waiting_for_new_department = State()
    confirmation = State()

class QrCreateStates(StatesGroup):
    confirmation = State()

class QrAssignStates(StatesGroup):
    waiting_for_qr_id = State()
    waiting_for_device = State()

class MoveDeviceStates(StatesGroup):
    waiting_for_device = State()
    waiting_for_employee = State()

# ---------- Функция возврата в главное меню ----------
async def back_to_main_menu(callback_or_message, user_id):
    admin_flag = await is_admin(user_id)
    kb = main_menu_keyboard(admin_flag)
    if isinstance(callback_or_message, CallbackQuery):
        await callback_or_message.message.answer("Главное меню:", reply_markup=kb)
        await callback_or_message.answer()
    else:
        await callback_or_message.answer("Главное меню:", reply_markup=kb)

# ---------- Функция для разбивки длинных сообщений ----------
async def send_long_message(target, text):
    if len(text) > 4000:
        for i in range(0, len(text), 4000):
            await target.answer(text[i:i+4000])
    else:
        await target.answer(text)

# ---------- Обработчики ----------
@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery):
    await back_to_main_menu(callback, callback.from_user.id)

@router.callback_query(F.data == "cancel")
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Действие отменено.")
    await back_to_main_menu(callback, callback.from_user.id)