import os
import requests
import qrcode
from PIL import Image, ImageDraw, ImageFont
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

BOT_USERNAME = settings.TELEGRAM_BOT_USERNAME

def generate_qr_image_for_device(device, target_dir=None):
    qr_code = device.qr_code
    qr_data = f"https://t.me/{BOT_USERNAME}?start={qr_code.code}"

    if target_dir is None:
        target_dir = os.path.join(settings.MEDIA_ROOT, 'qrcodes')
    os.makedirs(target_dir, exist_ok=True)
    filename = f"{device.inventory_number}.png"
    filepath = os.path.join(target_dir, filename)

    # Пытаемся использовать внешний API с таймаутом
    try:
        api_url = "https://api.qrserver.com/v1/create-qr-code/"
        params = {
            "data": qr_data,
            "size": "300x300",
            "margin": "1",
            "format": "png"
        }
        logger.info(f"Requesting device QR from API: {api_url} with data={qr_data}")
        response = requests.get(api_url, params=params, timeout=5)  # таймаут 5 сек
        response.raise_for_status()
        temp_path = filepath + ".tmp"
        with open(temp_path, 'wb') as f:
            f.write(response.content)
        _add_text_to_qr_image(temp_path, filepath, device, qr_code)
        os.remove(temp_path)
        logger.info(f"Device QR saved to {filepath} via API + text overlay")
        return filepath
    except Exception as e:
        logger.error(f"API failed for device QR: {e}, using local fallback")
        return _generate_device_qr_local(device, filepath)

def generate_simple_qr_image_api(code, target_dir=None):
    if target_dir is None:
        target_dir = os.path.join(settings.MEDIA_ROOT, 'qrcodes')
    os.makedirs(target_dir, exist_ok=True)
    filename = f"{code}.png"
    filepath = os.path.join(target_dir, filename)
    qr_data = f"https://t.me/{BOT_USERNAME}?start={code}"

    try:
        api_url = "https://api.qrserver.com/v1/create-qr-code/"
        params = {"data": qr_data, "size": "300x300", "margin": "1", "format": "png"}
        logger.info(f"Requesting simple QR from API: {api_url} with data={qr_data}")
        response = requests.get(api_url, params=params, timeout=5)
        response.raise_for_status()
        with open(filepath, 'wb') as f:
            f.write(response.content)
        logger.info(f"Simple QR saved to {filepath} via API")
        return filepath
    except Exception as e:
        logger.error(f"API failed for simple QR: {e}, using local fallback")
        return _generate_simple_qr_local(code, filepath, with_link=True)

# ... остальные функции без изменений ...