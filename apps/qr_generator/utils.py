import io
import logging
import os

import qrcode
from PIL import Image
from django.conf import settings
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)


def _build_start_link(code: str) -> str:
    username = (getattr(settings, "TELEGRAM_BOT_USERNAME", "") or "").strip().lstrip("@")
    if username:
        return f"https://t.me/{username}?start={code}"

    logger.warning(
        "TELEGRAM_BOT_USERNAME is empty. QR fallback uses plain code payload; deep-link scan won't auto-open bot."
    )
    return code


def _build_qr_image(data: str, box_size: int = 10, border: int = 2) -> Image.Image:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB")


def build_qr_png_content(data: str) -> ContentFile:
    qr_img = _build_qr_image(data)
    buffer = io.BytesIO()
    qr_img.save(buffer, format="PNG")
    return ContentFile(buffer.getvalue())


def generate_qr_image_for_device(device, target_dir=None):
    qr_code = device.qr_code
    qr_data = _build_start_link(qr_code.code)

    if target_dir is None:
        target_dir = os.path.join(settings.MEDIA_ROOT, "qrcodes")
    os.makedirs(target_dir, exist_ok=True)

    filepath = os.path.join(target_dir, f"{device.inventory_number}.png")

    try:
        qr_img = _build_qr_image(qr_data)
        qr_img.save(filepath, format="PNG")
        logger.info("Device QR saved to %s", filepath)
        return filepath
    except Exception:
        logger.exception("Failed generating device QR for device_id=%s", device.id)
        return None


def generate_simple_qr_image_api(code, target_dir=None):
    if target_dir is None:
        target_dir = os.path.join(settings.MEDIA_ROOT, "qrcodes")
    os.makedirs(target_dir, exist_ok=True)

    filepath = os.path.join(target_dir, f"{code}.png")
    qr_data = _build_start_link(code)

    try:
        qr_img = _build_qr_image(qr_data)
        qr_img.save(filepath, format="PNG")
        logger.info("Simple QR saved to %s", filepath)
        return filepath
    except Exception:
        logger.exception("Failed generating simple QR for code=%s", code)
        return None
