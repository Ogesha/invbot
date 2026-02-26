import logging
import os

import qrcode
from PIL import Image, ImageDraw, ImageFont
from django.conf import settings

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
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB")


def _get_font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except Exception:
        return ImageFont.load_default()


def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _compose_device_qr(qr_img: Image.Image, device, qr_code) -> Image.Image:
    width, height = qr_img.size
    canvas_height = height + 110
    canvas = Image.new("RGB", (width, canvas_height), "white")
    canvas.paste(qr_img, (0, 0))

    draw = ImageDraw.Draw(canvas)
    title_font = _get_font(18)
    body_font = _get_font(14)

    lines = [
        f"Инв. №: {device.inventory_number}",
        f"{device.name}",
        f"ID SQL: {qr_code.id}",
    ]
    y = height + 8
    for i, line in enumerate(lines):
        font = title_font if i == 0 else body_font
        text_w, text_h = _text_size(draw, line, font)
        draw.text(((width - text_w) // 2, y), line, fill="black", font=font)
        y += text_h + 4

    return canvas


def generate_qr_image_for_device(device, target_dir=None):
    qr_code = device.qr_code
    qr_data = _build_start_link(qr_code.code)

    if target_dir is None:
        target_dir = os.path.join(settings.MEDIA_ROOT, "qrcodes")
    os.makedirs(target_dir, exist_ok=True)

    filepath = os.path.join(target_dir, f"{device.inventory_number}.png")

    try:
        qr_img = _build_qr_image(qr_data)
        composed = _compose_device_qr(qr_img, device, qr_code)
        composed.save(filepath, format="PNG")
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
