from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from apps.bot.keyboards.inline import main_menu_keyboard
from apps.bot.utils.db import is_admin

router = Router()

@router.message(Command("menu"))
async def cmd_menu(message: Message):
    admin = await is_admin(message.from_user.id)
    await message.answer("Главное меню:", reply_markup=main_menu_keyboard(admin))

@router.callback_query(F.data == "ignore")
async def ignore_callback(callback: CallbackQuery):
    await callback.answer()

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=main_menu_keyboard(await is_admin(message.from_user.id)))

@router.callback_query(F.data == "cancel")
async def callback_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Действие отменено.")
    admin = await is_admin(callback.from_user.id)
    await callback.message.answer("Главное меню:", reply_markup=main_menu_keyboard(admin))
    await callback.answer()