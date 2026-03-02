from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from asgiref.sync import sync_to_async
from aiogram.exceptions import TelegramBadRequest

from ...utils.db import (
    is_admin, create_qr_code, assign_qr_to_device,
    get_qr_data, get_all_qr_codes_data, get_free_qr_codes_data,
    regenerate_qr_image, get_devices_without_qr
)
from ...keyboards.inline import (
    confirm_keyboard, cancel_keyboard, device_list_keyboard,
    qr_list_keyboard, free_qr_list_keyboard, qr_detail_keyboard
)
from ...notifications import send_photo_sync
from .common import back_to_main_menu, QrCreateStates, QrAssignStates

router = Router()

# ---------- Раздел "QR-коды" ----------
@router.callback_query(F.data == "admin_qr_menu")
async def qr_menu(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📋 Все QR-коды", callback_data="admin_list_qrs"))
    builder.row(InlineKeyboardButton(text="➕ Создать QR-код", callback_data="admin_create_qr"))
    builder.row(InlineKeyboardButton(text="🆓 Свободные QR", callback_data="admin_free_qrs_list"))
    builder.row(InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main"))
    await callback.message.edit_text("🔹 Управление QR-кодами:", reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(F.data == "admin_list_qrs")
async def list_all_qrs(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    page = 1
    data = await get_all_qr_codes_data(page=page)
    kb = qr_list_keyboard(data['items'], page, data['total_pages'], action_prefix="qr")
    try:
        await callback.message.edit_text(
            f"Все QR-коды (страница {page}/{data['total_pages']}):",
            reply_markup=kb
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await callback.answer()
        else:
            raise e
    await callback.answer()

@router.callback_query(F.data.startswith("qr_page_"))
async def paginate_qr_list(callback: CallbackQuery):
    page = int(callback.data.split("_")[-1])
    data = await get_all_qr_codes_data(page=page)
    kb = qr_list_keyboard(data['items'], page, data['total_pages'], action_prefix="qr")
    try:
        await callback.message.edit_reply_markup(reply_markup=kb)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await callback.answer()
        else:
            raise e
    await callback.answer()

@router.callback_query(F.data.startswith("qr_detail_"))
async def qr_detail(callback: CallbackQuery):
    qr_id = int(callback.data.split("_")[-1])
    qr_data = await get_qr_data(qr_id)
    if not qr_data:
        await callback.message.edit_text("QR-код не найден.")
        await callback.answer()
        return
    device_info = f"Устройство: {qr_data.device.inventory_number}" if qr_data.device else "Свободен"
    text = (
        f"🔹 <b>QR-код ID {qr_data.id}</b>\n"
        f"Код: {qr_data.code}\n"
        f"Создан: {qr_data.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"Активен: {'✅' if qr_data.is_active else '❌'}\n"
        f"{device_info}"
    )
    is_free = qr_data.device is None
    kb = qr_detail_keyboard(qr_data.id, is_free)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await callback.answer()
        else:
            raise e
    await callback.answer()

@router.callback_query(F.data.startswith("qr_regenerate_"))
async def qr_regenerate(callback: CallbackQuery):
    qr_id = int(callback.data.split("_")[-1])
    success, msg = await regenerate_qr_image(qr_id)
    await callback.message.edit_text(msg)
    await back_to_main_menu(callback, callback.from_user.id)

@router.callback_query(F.data.startswith("qr_delete_"))
async def qr_delete_confirm(callback: CallbackQuery):
    qr_id = int(callback.data.split("_")[-1])
    qr_data = await get_qr_data(qr_id)
    if not qr_data:
        await callback.message.edit_text("QR-код не найден.")
        return
    text = f"❓ Удалить QR-код ID {qr_data.id} (код {qr_data.code})?"
    kb = confirm_keyboard(f"qr_delete_yes_{qr_id}", f"qr_delete_no_{qr_id}")
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await callback.answer()
        else:
            raise e
    await callback.answer()

@router.callback_query(F.data.startswith("qr_delete_yes_"))
async def qr_delete_execute(callback: CallbackQuery):
    qr_id = int(callback.data.split("_")[-1])
    from apps.core.models import QRCode
    try:
        qr = await sync_to_async(QRCode.objects.get)(id=qr_id)
        await sync_to_async(qr.delete)()
        await callback.message.edit_text("✅ QR-код удалён.")
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка: {e}")
    await back_to_main_menu(callback, callback.from_user.id)

@router.callback_query(F.data == "admin_create_qr")
async def create_qr_start(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    await callback.message.edit_text(
        "Вы хотите создать новый QR‑код (будет сгенерирован автоматически).",
        reply_markup=confirm_keyboard("createqr_yes", "createqr_no")
    )
    await state.set_state(QrCreateStates.confirmation)
    await callback.answer()

@router.callback_query(QrCreateStates.confirmation, F.data == "createqr_yes")
async def create_qr_execute(callback: CallbackQuery, state: FSMContext):
    qr = await create_qr_code(callback.from_user.id)
    await callback.message.edit_text(
        f"✅ QR‑код создан!\nID: {qr.id}\nКод: {qr.code}"
    )
    if qr.image:
        send_photo_sync(callback.from_user.id, qr.image.path, caption=f"Ваш новый QR‑код (ID {qr.id})")
    await state.clear()
    await back_to_main_menu(callback, callback.from_user.id)

@router.callback_query(F.data == "createqr_no")
async def create_qr_cancel(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("❌ Создание отменено.")
    await state.clear()
    await back_to_main_menu(callback, callback.from_user.id)

@router.callback_query(F.data == "admin_free_qrs_list")
async def list_free_qrs(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    page = 1
    data = await get_free_qr_codes_data(page=page)
    kb = free_qr_list_keyboard(data['items'], page, data['total_pages'], action_prefix="freeqr")
    try:
        await callback.message.edit_text(
            f"Свободные QR-коды (страница {page}/{data['total_pages']}):",
            reply_markup=kb
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await callback.answer()
        else:
            raise e
    await callback.answer()

@router.callback_query(F.data.startswith("freeqr_page_"))
async def paginate_free_qrs(callback: CallbackQuery):
    page = int(callback.data.split("_")[-1])
    data = await get_free_qr_codes_data(page=page)
    kb = free_qr_list_keyboard(data['items'], page, data['total_pages'], action_prefix="freeqr")
    try:
        await callback.message.edit_reply_markup(reply_markup=kb)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await callback.answer()
        else:
            raise e
    await callback.answer()

@router.callback_query(F.data.startswith("freeqr_select_"))
async def select_free_qr(callback: CallbackQuery, state: FSMContext):
    qr_id = int(callback.data.split("_")[-1])
    await state.update_data(qr_id=qr_id)
    # Показываем только устройства без QR
    devices = await get_devices_without_qr(callback.from_user.id)
    if not devices:
        await callback.message.edit_text("Нет доступных устройств без QR.")
        await state.clear()
        await back_to_main_menu(callback, callback.from_user.id)
        return
    kb = device_list_keyboard(devices)
    await callback.message.edit_text("Выберите устройство для привязки:", reply_markup=kb)
    await state.set_state(QrAssignStates.waiting_for_device)
    await callback.answer()

@router.callback_query(QrAssignStates.waiting_for_device, F.data.startswith("dev_"))
async def process_device_select(callback: CallbackQuery, state: FSMContext):
    device_id = int(callback.data.split("_")[-1])
    data = await state.get_data()
    qr_id = data['qr_id']
    success, msg = await assign_qr_to_device(qr_id, device_id, callback.from_user.id)
    await callback.message.edit_text(msg)
    await state.clear()
    await back_to_main_menu(callback, callback.from_user.id)

@router.callback_query(F.data == "admin_assign_qr")
async def assign_qr_start(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📋 Выбрать из свободных", callback_data="admin_free_qrs_list"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
    await callback.message.edit_text(
        "Введите ID QR‑кода или выберите из списка:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(QrAssignStates.waiting_for_qr_id)
    await callback.answer()