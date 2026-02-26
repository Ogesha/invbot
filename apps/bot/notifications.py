import logging
import requests
import time
from aiogram import Bot
from django.conf import settings
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)
bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)

@sync_to_async
def get_admin_telegram_ids():
    from apps.core.models import Employee
    return list(Employee.objects.filter(is_admin=True, is_approved=True, telegram_id__isnull=False).values_list('telegram_id', flat=True))

async def notify_admins_about_request(request):
    admin_ids = await get_admin_telegram_ids()
    if not admin_ids:
        logger.warning("No admin IDs found to notify about registration request")
        return
    text = (
        f"🆕 Новая заявка на регистрацию!\n"
        f"👤 ФИО: {request.full_name}\n"
        f"🆔 Telegram ID: {request.telegram_id}\n"
        f"📱 Username: @{request.telegram_username if request.telegram_username else '—'}\n"
        f"Для подтверждения зайдите в админку."
    )
    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, text)
            logger.info(f"Notification sent to admin {admin_id}")
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}", exc_info=True)

async def notify_user_about_approval(telegram_id, full_name):
    try:
        await bot.send_message(
            telegram_id,
            f"✅ Ваша заявка на регистрацию одобрена! Добро пожаловать, {full_name}.\n"
            f"Теперь вы можете пользоваться ботом. Напишите /start для начала работы."
        )
        logger.info(f"Approval notification sent to {telegram_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send approval notification to {telegram_id}: {e}", exc_info=True)
        return False

async def notify_user_about_rejection(telegram_id, full_name, comment=""):
    text = f"❌ Ваша заявка на регистрацию отклонена."
    if comment:
        text += f"\nКомментарий: {comment}"
    try:
        await bot.send_message(telegram_id, text)
        logger.info(f"Rejection notification sent to {telegram_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send rejection notification to {telegram_id}: {e}", exc_info=True)
        return False

def send_message_sync(chat_id, text):
    """Синхронная отправка сообщения через requests (без asyncio)"""
    token = settings.TELEGRAM_BOT_TOKEN
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text}
    try:
        response = requests.post(url, data=payload, timeout=5)
        response.raise_for_status()
        logger.info(f"Sync message sent to {chat_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send sync message to {chat_id}: {e}", exc_info=True)
        return False

def send_log_to_group_sync(message: str):
    """Отправить сообщение в группу/канал для логов (синхронно)"""
    print(f"!!! send_log_to_group_sync: {message}")
    group_id = settings.TELEGRAM_LOG_GROUP_ID
    if not group_id:
        logger.warning("TELEGRAM_LOG_GROUP_ID not set, log message dropped")
        return
    send_message_sync(group_id, message)

def send_photo_sync(chat_id, photo_path, caption=None, retries=3):
    """
    Синхронная отправка фото через requests с повторными попытками при ошибке 429.
    """
    token = settings.TELEGRAM_BOT_TOKEN
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    for attempt in range(retries):
        try:
            with open(photo_path, 'rb') as photo:
                files = {'photo': photo}
                data = {'chat_id': chat_id}
                if caption:
                    data['caption'] = caption
                response = requests.post(url, data=data, files=files, timeout=10)
                response.raise_for_status()
                logger.info(f"Photo sent to {chat_id}")
                return True
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429 and attempt < retries - 1:
                wait = 2 ** attempt  # экспоненциальная задержка: 1, 2, 4 секунды
                logger.warning(f"Rate limited (429), waiting {wait}s before retry {attempt+1}/{retries}")
                time.sleep(wait)
            else:
                logger.error(f"Failed to send photo to {chat_id}: {e}", exc_info=True)
                return False
        except Exception as e:
            logger.error(f"Failed to send photo to {chat_id}: {e}", exc_info=True)
            return False