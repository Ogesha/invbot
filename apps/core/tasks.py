from celery import shared_task
from django.core.files import File
import os
import logging

from .models import Device, QRCode
from ..qr_generator.utils import generate_qr_image_for_device

logger = logging.getLogger(__name__)

@shared_task
def generate_qr_codes_for_devices(device_ids, target_dir=None):
    """
    Асинхронная генерация QR-кодов для списка устройств.
    Возвращает словарь с результатами.
    """
    devices = Device.objects.filter(id__in=device_ids)
    total = devices.count()
    success = 0
    errors = []
    for device in devices:
        try:
            qr, created = QRCode.objects.get_or_create(device=device)
            filepath = generate_qr_image_for_device(device, target_dir)
            if filepath and os.path.exists(filepath):
                with open(filepath, 'rb') as f:
                    qr.image.save(os.path.basename(filepath), File(f), save=False)
                qr.save(update_fields=['image'])
            success += 1
        except Exception as e:
            errors.append(str(e))
            logger.error(f"Error generating QR for device {device.id}: {e}")
    return {
        'total': total,
        'success': success,
        'errors': errors,
        'target_dir': target_dir or 'default',
    }