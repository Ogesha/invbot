import os
import logging
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from django.conf import settings
from .models import (
    Department, Employee, Device, Computer, Printer,
    QRCode, RegistrationRequest, DeviceHistory
)
from .utils import send_log_to_group_sync
from ..bot.notifications import send_photo_sync

print("=== signals.py успешно загружен ===")
logger = logging.getLogger(__name__)


def get_changed_fields(old_instance, new_instance, field_names):
    changes = []
    for field in field_names:
        old_val = getattr(old_instance, field)
        new_val = getattr(new_instance, field)
        if old_val != new_val:
            if hasattr(old_val, '__str__'):
                old_str = str(old_val)
            else:
                old_str = old_val if old_val is not None else '—'
            if hasattr(new_val, '__str__'):
                new_str = str(new_val)
            else:
                new_str = new_val if new_val is not None else '—'
            changes.append(f"  - {field}: {old_str} -> {new_str}")
    return changes


def format_device_message(instance, action, changes=None):
    base = f"{action} {instance.__class__.__name__.lower()}: {instance.inventory_number} – {instance.name}"
    if changes:
        return base + "\n" + "\n".join(changes)
    return base


# ----- Сигнал для всех устройств (Computer, Printer и др.) -----
@receiver(pre_save)
def device_pre_save_handler(sender, instance, **kwargs):
    if not isinstance(instance, Device):
        return

    print(f"!!! device_pre_save_handler для {instance.__class__.__name__} id={instance.pk}")

    if not instance.pk:
        return

    try:
        old = Device.objects.select_related('responsible', 'department').get(pk=instance.pk)
    except Device.DoesNotExist:
        return

    changes = []

    if old.responsible != instance.responsible:
        old_resp_str = str(old.responsible) if old.responsible else '—'
        new_resp_str = str(instance.responsible) if instance.responsible else '—'
        DeviceHistory.objects.create(
            device=instance,
            field='responsible',
            old_value=old_resp_str,
            new_value=new_resp_str
        )
        changes.append(f"Ответственный: {old_resp_str} → {new_resp_str}")

    if old.department != instance.department:
        old_dept_str = old.department.name if old.department else '—'
        new_dept_str = instance.department.name if instance.department else '—'
        DeviceHistory.objects.create(
            device=instance,
            field='department',
            old_value=old_dept_str,
            new_value=new_dept_str
        )
        changes.append(f"Отдел: {old_dept_str} → {new_dept_str}")

    if old.status != instance.status:
        old_status_str = old.get_status_display()
        new_status_str = instance.get_status_display()
        DeviceHistory.objects.create(
            device=instance,
            field='status',
            old_value=old_status_str,
            new_value=new_status_str
        )
        changes.append(f"Статус: {old_status_str} → {new_status_str}")

    if changes:
        msg = f"✏️ Изменено устройство: {instance.inventory_number} – {instance.name}\n" + "\n".join(changes)
        send_log_to_group_sync(msg)


@receiver(post_save)
def create_qr_for_device(sender, instance, created, **kwargs):
    # Игнорируем обновления, вызванные изменением QR-кода (чтобы избежать цикла)
    if kwargs.get('update_fields') is not None and 'qr_code' in kwargs['update_fields']:
        return
    if not isinstance(instance, Device):
        return
    if created:
        QRCode.objects.get_or_create(device=instance)
        msg = f"🆕 Создано новое устройство: {instance.inventory_number} – {instance.name}"
        send_log_to_group_sync(msg)


@receiver(post_delete)
def log_device_delete(sender, instance, **kwargs):
    if not isinstance(instance, Device):
        return
    msg = f"🗑 Удалено устройство: {instance.inventory_number} – {instance.name}"
    send_log_to_group_sync(msg)


# ----- Сигналы для отделов -----
@receiver(post_save, sender=Department)
def log_department_save(sender, instance, created, **kwargs):
    # Игнорируем автоматические обновления служебных полей (если есть)
    if kwargs.get('update_fields') is not None and 'image' in kwargs['update_fields']:
        return
    action = "Создан" if created else "Изменён"
    msg = f"{action} отдел: {instance.name}"
    send_log_to_group_sync(msg)


@receiver(post_delete, sender=Department)
def log_department_delete(sender, instance, **kwargs):
    msg = f"Удалён отдел: {instance.name}"
    send_log_to_group_sync(msg)


# ----- Сигналы для сотрудников -----
@receiver(post_save, sender=Employee)
def log_employee_save(sender, instance, created, **kwargs):
    # Игнорируем автоматические обновления служебных полей (если есть)
    if kwargs.get('update_fields') is not None and 'image' in kwargs['update_fields']:
        return
    action = "Создан" if created else "Изменён"
    dept = f" (отдел: {instance.department.name})" if instance.department else ""
    msg = f"{action} сотрудник: {instance.full_name}{dept}"
    send_log_to_group_sync(msg)


@receiver(post_delete, sender=Employee)
def log_employee_delete(sender, instance, **kwargs):
    msg = f"Удалён сотрудник: {instance.full_name}"
    send_log_to_group_sync(msg)


# ----- Сигналы для QR-кодов -----
@receiver(post_save, sender=QRCode)
def log_qrcode_save(sender, instance, created, **kwargs):
    # Игнорируем обновления, вызванные только генерацией изображения
    if kwargs.get('update_fields') is not None and 'image' in kwargs['update_fields']:
        return

    action = "Создан" if created else "Изменён"
    device_info = f" для устройства {instance.device.inventory_number}" if instance.device else ""
    msg = f"{action} QR-код: {instance.code}{device_info}"

    group_id = settings.TELEGRAM_LOG_GROUP_ID
    if not group_id:
        return

    if instance.image and os.path.exists(instance.image.path):
        send_photo_sync(group_id, instance.image.path, caption=msg)
    else:
        send_log_to_group_sync(msg)


@receiver(post_delete, sender=QRCode)
def log_qrcode_delete(sender, instance, **kwargs):
    device_info = f" для устройства {instance.device.inventory_number}" if instance.device else ""
    msg = f"🗑 Удалён QR-код: {instance.code}{device_info}"
    send_log_to_group_sync(msg)


# ----- Сигналы для заявок на регистрацию -----
@receiver(post_save, sender=RegistrationRequest)
def log_regrequest_save(sender, instance, created, **kwargs):
    # Игнорируем автоматические обновления служебных полей (если есть)
    if kwargs.get('update_fields') is not None and 'image' in kwargs['update_fields']:
        return
    action = "Создана" if created else "Изменена"
    msg = f"{action} заявка на регистрацию: {instance.full_name} (ID {instance.telegram_id})"
    send_log_to_group_sync(msg)


@receiver(post_delete, sender=RegistrationRequest)
def log_regrequest_delete(sender, instance, **kwargs):
    msg = f"Удалена заявка на регистрацию: {instance.full_name} (ID {instance.telegram_id})"
    send_log_to_group_sync(msg)


# ----- Сигнал для удаления заявки при удалении сотрудника -----
@receiver(post_delete, sender=Employee)
def delete_related_registration_request(sender, instance, **kwargs):
    if instance.telegram_id:
        RegistrationRequest.objects.filter(telegram_id=instance.telegram_id).delete()