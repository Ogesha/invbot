import logging
import requests
import time
from aiogram import Bot
from django.conf import settings
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)
bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)

_TOPIC_TITLES = {
    'error': '❌ Ошибки',
    'employee': '👥 Сотрудники',
    'device': '💻 Техника',
    'department': '🏢 Отделы',
    'qr': '🔳 QR-коды',
    'request': '📝 Заявки',
    'other': '📌 Прочее',
}
_TOPIC_CACHE = {}


def _telegram_method_url(method: str) -> str:
    token = settings.TELEGRAM_BOT_TOKEN
    return f"https://api.telegram.org/bot{token}/{method}"


def _detect_log_type(message: str) -> str:
    text = (message or '').lower()
    if any(key in text for key in ('ошиб', 'exception', 'traceback', '❌')):
        return 'error'
    if any(key in text for key in ('сотрудник', 'администратор')):
        return 'employee'
    if any(key in text for key in ('устройств', 'техник', 'инвентар')):
        return 'device'
    if 'отдел' in text:
        return 'department'
    if 'qr' in text:
        return 'qr'
    if 'заявк' in text:
        return 'request'
    return 'other'


def _create_forum_topic(chat_id: int, topic_name: str):
    try:
        response = requests.post(
            _telegram_method_url('createForumTopic'),
            data={'chat_id': chat_id, 'name': topic_name},
            timeout=8,
        )
        response.raise_for_status()
        payload = response.json() or {}
        if not payload.get('ok'):
            logger.warning('createForumTopic failed: %s', payload)
            return None
        result = payload.get('result') or {}
        return result.get('message_thread_id')
    except Exception:
        logger.exception('Failed to create forum topic in chat %s (%s)', chat_id, topic_name)
        return None


def _get_or_create_topic_thread(chat_id: int, log_type: str):
    cache_key = f'{chat_id}:{log_type}'
    if cache_key in _TOPIC_CACHE:
        return _TOPIC_CACHE[cache_key]

    topic_name = _TOPIC_TITLES.get(log_type, _TOPIC_TITLES['other'])
    thread_id = _create_forum_topic(chat_id, topic_name)
    if thread_id:
        _TOPIC_CACHE[cache_key] = thread_id
    return thread_id


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


def send_message_sync(chat_id, text, message_thread_id=None):
    """Синхронная отправка сообщения через requests (без asyncio)"""
    payload = {'chat_id': chat_id, 'text': text}
    if message_thread_id:
        payload['message_thread_id'] = message_thread_id
    try:
        response = requests.post(_telegram_method_url('sendMessage'), data=payload, timeout=5)
        response.raise_for_status()
        logger.info(f"Sync message sent to {chat_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send sync message to {chat_id}: {e}", exc_info=True)
        return False


def send_log_to_group_sync(message: str, log_type: str | None = None):
    """Отправить сообщение в лог-группу, используя темы по типам событий."""
    print(f"!!! send_log_to_group_sync: {message}")
    group_id = settings.TELEGRAM_LOG_GROUP_ID
    if not group_id:
        logger.warning("TELEGRAM_LOG_GROUP_ID not set, log message dropped")
        return

    event_type = log_type or _detect_log_type(message)
    thread_id = _get_or_create_topic_thread(group_id, event_type)
    send_message_sync(group_id, message, message_thread_id=thread_id)


def send_photo_sync(chat_id, photo_path, caption=None, retries=3, message_thread_id=None, log_type=None):
    """
    Синхронная отправка фото через requests с повторными попытками при ошибке 429.
    """
    if message_thread_id is None and chat_id == settings.TELEGRAM_LOG_GROUP_ID:
        event_type = log_type or _detect_log_type(caption or '')
        message_thread_id = _get_or_create_topic_thread(chat_id, event_type)

    url = _telegram_method_url('sendPhoto')
    for attempt in range(retries):
        try:
            with open(photo_path, 'rb') as photo:
                files = {'photo': photo}
                data = {'chat_id': chat_id}
                if caption:
                    data['caption'] = caption
                if message_thread_id:
                    data['message_thread_id'] = message_thread_id
                response = requests.post(url, data=data, files=files, timeout=10)
                response.raise_for_status()
                logger.info(f"Photo sent to {chat_id}")
                return True
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429 and attempt < retries - 1:
                wait = 2 ** attempt
                logger.warning(f"Rate limited (429), waiting {wait}s before retry {attempt+1}/{retries}")
                time.sleep(wait)
            else:
                logger.error(f"Failed to send photo to {chat_id}: {e}", exc_info=True)
                return False
        except Exception as e:
            logger.error(f"Failed to send photo to {chat_id}: {e}", exc_info=True)
            return False
