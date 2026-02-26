from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def main_menu_keyboard(is_admin: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if is_admin:
        builder.row(InlineKeyboardButton(text="➕ Добавить сотрудника", callback_data="admin_add_employee"))
        builder.row(
            InlineKeyboardButton(text="👥 Сотрудники", callback_data="admin_employees_menu"),
            InlineKeyboardButton(text="🏢 Отделы", callback_data="admin_departments_menu")
        )
        builder.row(
            InlineKeyboardButton(text="🔹 Управление QR", callback_data="admin_qr_menu")
        )
    else:
        builder.row(InlineKeyboardButton(text="ℹ️ Как сканировать QR", callback_data="qr_info"))
    return builder.as_markup()

def departments_keyboard(departments, action_prefix="dept") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for dept in departments:
        builder.button(text=dept.name, callback_data=f"{action_prefix}_{dept.id}")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="🔙 Назад в главное меню", callback_data="back_to_main"))
    return builder.as_markup()

def employees_by_department_keyboard(employees, department_id, page=1, items_per_page=5) -> InlineKeyboardMarkup:
    from math import ceil
    total_pages = ceil(len(employees) / items_per_page)
    start = (page - 1) * items_per_page
    end = start + items_per_page
    page_emps = employees[start:end]

    builder = InlineKeyboardBuilder()
    for emp in page_emps:
        builder.button(
            text=f"{emp.full_name} {'✅' if emp.is_approved else '⏳'}",
            callback_data=f"emp_edit_{emp.id}"
        )
    builder.adjust(1)

    if total_pages > 1:
        nav_row = []
        if page > 1:
            nav_row.append(InlineKeyboardButton(
                text="◀️ Пред.",
                callback_data=f"dept_emps_page_{department_id}_{page-1}"
            ))
        nav_row.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="ignore"))
        if page < total_pages:
            nav_row.append(InlineKeyboardButton(
                text="След. ▶️",
                callback_data=f"dept_emps_page_{department_id}_{page+1}"
            ))
        builder.row(*nav_row)

    builder.row(InlineKeyboardButton(text="➕ Добавить сотрудника", callback_data="admin_add_employee"))
    builder.row(InlineKeyboardButton(text="🔙 К списку отделов", callback_data="admin_departments_menu"))
    builder.row(InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main"))
    return builder.as_markup()

def employee_edit_keyboard(employee_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✏️ Изменить ФИО", callback_data=f"emp_edit_name_{employee_id}"),
        InlineKeyboardButton(text="🔄 Сменить отдел", callback_data=f"emp_edit_dept_{employee_id}")
    )
    builder.row(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"emp_approve_{employee_id}"),
        InlineKeyboardButton(text="❌ Удалить", callback_data=f"emp_delete_{employee_id}")
    )
    builder.row(
        InlineKeyboardButton(text="📋 Техника сотрудника", callback_data=f"emp_devices_{employee_id}")
    )
    builder.row(InlineKeyboardButton(text="🔙 К списку сотрудников", callback_data=f"back_to_dept_emps_{employee_id}"))
    return builder.as_markup()

def devices_list_keyboard(devices, page, total_pages, action_prefix="device_detail") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for device in devices:
        builder.row(InlineKeyboardButton(
            text=f"{device.inventory_number} – {device.name[:20]}",
            callback_data=f"{action_prefix}_{device.id}"
        ))
    if total_pages > 1:
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"{action_prefix.split('_')[0]}_page_{page-1}"))
        nav_buttons.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="current_page"))
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"{action_prefix.split('_')[0]}_page_{page+1}"))
        builder.row(*nav_buttons)
    return builder.as_markup()

def device_detail_keyboard(device_id: int, is_owner: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Назад к списку", callback_data="my_devices"))
    return builder.as_markup()

def types_keyboard(types) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for t in types:
        builder.button(text=t.name, callback_data=f"type_{t.id}")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
    return builder.as_markup()

def device_types_keyboard(types, action_prefix="list_filter_type") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for t in types:
        builder.button(text=t.name, callback_data=f"{action_prefix}_{t.id}")
    builder.button(text="Все типы", callback_data=f"{action_prefix}_all")
    builder.adjust(1)
    return builder.as_markup()

def status_keyboard(action_prefix="list_filter_status") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ В эксплуатации", callback_data=f"{action_prefix}_active")
    builder.button(text="❌ Не в эксплуатации", callback_data=f"{action_prefix}_inactive")
    builder.button(text="Все", callback_data=f"{action_prefix}_all")
    builder.adjust(1)
    return builder.as_markup()

def confirm_keyboard(yes_data: str, no_data: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да", callback_data=yes_data)
    builder.button(text="❌ Нет", callback_data=no_data)
    builder.adjust(2)
    return builder.as_markup()

def cancel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="cancel")
    return builder.as_markup()

def device_list_keyboard(devices) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for dev in devices[:10]:
        builder.button(
            text=f"{dev.inventory_number} – {dev.name[:20]}",
            callback_data=f"dev_{dev.id}"
        )
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
    return builder.as_markup()

def qr_list_keyboard(qr_items, page, total_pages, action_prefix="qr") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for qr in qr_items:
        status = "✅" if qr['is_active'] else "❌"
        device = f" (устр.{qr['device_inventory']})" if qr['device_inventory'] else " (свободен)"
        builder.button(
            text=f"{status} {qr['code'][:8]}...{device}",
            callback_data=f"{action_prefix}_detail_{qr['id']}"
        )
    builder.adjust(1)

    if total_pages > 1:
        nav_row = []
        if page > 1:
            nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"{action_prefix}_page_{page-1}"))
        nav_row.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="ignore"))
        if page < total_pages:
            nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"{action_prefix}_page_{page+1}"))
        builder.row(*nav_row)

    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main"))
    return builder.as_markup()

def free_qr_list_keyboard(qr_items, page, total_pages, action_prefix="freeqr") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for qr in qr_items:
        builder.button(
            text=f"ID {qr['id']}: {qr['code'][:12]}...",
            callback_data=f"{action_prefix}_select_{qr['id']}"
        )
    builder.adjust(1)

    if total_pages > 1:
        nav_row = []
        if page > 1:
            nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"{action_prefix}_page_{page-1}"))
        nav_row.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="ignore"))
        if page < total_pages:
            nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"{action_prefix}_page_{page+1}"))
        builder.row(*nav_row)

    builder.row(InlineKeyboardButton(text="🔙 Отмена", callback_data="cancel"))
    return builder.as_markup()

def qr_detail_keyboard(qr_id: int, is_free: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if is_free:
        builder.row(InlineKeyboardButton(text="🔗 Привязать к устройству", callback_data=f"qr_assign_{qr_id}"))
    builder.row(InlineKeyboardButton(text="🔄 Перегенерировать", callback_data=f"qr_regenerate_{qr_id}"))
    builder.row(InlineKeyboardButton(text="❌ Удалить", callback_data=f"qr_delete_{qr_id}"))
    builder.row(InlineKeyboardButton(text="🔙 К списку", callback_data="admin_list_qrs"))
    return builder.as_markup()