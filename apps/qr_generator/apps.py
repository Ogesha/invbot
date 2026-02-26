from django.apps import AppConfig

class QrGeneratorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.qr_generator'
    verbose_name = 'Генерация QR-кодов'