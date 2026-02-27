import uuid
from django.db import models
from django.core.exceptions import ValidationError

class Department(models.Model):
    name = models.CharField("Название", max_length=100, unique=True)
    description = models.TextField("Описание", blank=True)

    class Meta:
        verbose_name = "Отдел"
        verbose_name_plural = "Отделы"

    def __str__(self):
        return self.name


class Employee(models.Model):
    full_name = models.CharField("ФИО", max_length=150)
    position = models.CharField("Должность", max_length=100, blank=True)
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True,
        verbose_name="Отдел", blank=True, related_name='employees'
    )
    telegram_id = models.BigIntegerField("Telegram ID", unique=True, null=True, blank=True)
    is_admin = models.BooleanField("Администратор", default=False)
    email = models.EmailField("Email", blank=True)
    phone = models.CharField("Телефон", max_length=20, blank=True)
    is_approved = models.BooleanField("Подтверждён", default=False)

    class Meta:
        verbose_name = "Сотрудник"
        verbose_name_plural = "Сотрудники"

    def __str__(self):
        if self.department:
            return f"{self.full_name} ({self.department.name})"
        return self.full_name


class RegistrationRequest(models.Model):
    telegram_id = models.BigIntegerField("Telegram ID", unique=True)
    telegram_username = models.CharField("Username", max_length=100, blank=True)
    full_name = models.CharField("ФИО", max_length=150)
    created_at = models.DateTimeField("Дата заявки", auto_now_add=True)
    is_processed = models.BooleanField("Обработано", default=False)
    approved = models.BooleanField("Одобрено", default=False)
    comment = models.TextField("Комментарий", blank=True)

    class Meta:
        verbose_name = "Заявка на регистрацию"
        verbose_name_plural = "Заявки на регистрацию"

    def __str__(self):
        return f"Заявка от {self.full_name} (ID {self.telegram_id})"


class DeviceType(models.Model):
    name = models.CharField("Название", max_length=50)
    code = models.CharField("Код", max_length=10, unique=True)

    class Meta:
        verbose_name = "Тип техники"
        verbose_name_plural = "Типы техники"

    def __str__(self):
        return self.name


class Device(models.Model):
    STATUS_CHOICES = [
        ('in_use', 'В эксплуатации'),
        ('not_in_use', 'Не в эксплуатации'),
        ('reserve', 'Резерв'),
    ]

    inventory_number = models.CharField("Инвентарный номер", max_length=50, unique=True)
    name = models.CharField("Наименование/модель", max_length=200)
    device_type = models.ForeignKey(
        DeviceType, on_delete=models.PROTECT, verbose_name="Тип техники",
        related_name='devices'
    )
    description = models.TextField("Описание", blank=True)
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True,
        verbose_name="Отдел", blank=True, related_name='devices'
    )
    responsible = models.ForeignKey(
        Employee, on_delete=models.SET_NULL, null=True,
        verbose_name="Ответственный", blank=True, related_name='devices'
    )
    status = models.CharField("Статус", max_length=20, choices=STATUS_CHOICES, default='in_use')
    serial_number = models.CharField("Серийный номер", max_length=100, blank=True)
    manufacturer = models.CharField("Производитель", max_length=100, blank=True)
    photo = models.ImageField("Фото", upload_to='devices/', blank=True, null=True)
    purchase_date = models.DateField("Дата покупки", null=True, blank=True)

    class Meta:
        verbose_name = "Техника (базовая модель)"
        verbose_name_plural = "Техника (базовая модель)"
        ordering = ['inventory_number']

    def __str__(self):
        return f"{self.inventory_number} – {self.name}"


class Computer(Device):
    processor = models.CharField("Процессор", max_length=100, blank=True)
    ram = models.CharField("Оперативная память", max_length=50, blank=True, help_text="например, 16 ГБ")
    disk_size = models.CharField("Объём диска", max_length=50, blank=True, help_text="например, 512 ГБ SSD")

    class Meta:
        verbose_name = "Компьютер"
        verbose_name_plural = "Компьютеры"

    def __str__(self):
        return f"{self.inventory_number} – {self.name} (ПК)"


class Printer(Device):
    COLOR_CHOICES = [
        ('color', 'Цветной'),
        ('bw', 'Чёрно-белый'),
    ]
    color_type = models.CharField("Тип печати", max_length=10, choices=COLOR_CHOICES, default='bw')
    paper_format = models.CharField("Формат печати", max_length=20, blank=True, help_text="например, A4, A3")

    class Meta:
        verbose_name = "Принтер"
        verbose_name_plural = "Принтеры"

    def __str__(self):
        return f"{self.inventory_number} – {self.name} (Принтер)"


class QRCode(models.Model):
    device = models.OneToOneField(
        Device, on_delete=models.SET_NULL, verbose_name="Техника",
        related_name='qr_code', null=True, blank=True
    )
    code = models.CharField("Уникальный код", max_length=50, unique=True, default=uuid.uuid4)
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)
    is_active = models.BooleanField("Активен", default=True)
    image = models.ImageField("Изображение QR", upload_to='qrcodes/', blank=True, null=True)

    class Meta:
        verbose_name = "QR-код"
        verbose_name_plural = "QR-коды"

    def save(self, *args, **kwargs):
        # Если код не задан, генерируем случайный UUID (первые 8 символов)
        if not self.code:
            self.code = str(uuid.uuid4())[:8]

        # Проверяем, изменилось ли устройство (для существующей записи)
        device_changed = False
        if self.pk:
            try:
                old = QRCode.objects.get(pk=self.pk)
                device_changed = old.device != self.device
            except QRCode.DoesNotExist:
                pass

        super().save(*args, **kwargs)

        # Генерируем изображение, если:
        # - есть устройство и (нет изображения ИЛИ устройство изменилось)
        if self.device and (not self.image or device_changed):
            self.generate_image()
        elif not self.device and not self.image:
            self.generate_simple_image()

    def generate_image(self):
        """Генерирует изображение QR для привязанной техники."""
        if not self.device:
            return

        from ..qr_generator.utils import _build_start_link, build_qr_png_content

        content = build_qr_png_content(_build_start_link(self.code))
        self.image.save(f"{self.device.inventory_number}.png", content, save=False)
        self.save(update_fields=['image'])

    def generate_simple_image(self):
        """Генерирует изображение QR только с кодом."""
        from ..qr_generator.utils import _build_start_link, build_qr_png_content

        content = build_qr_png_content(_build_start_link(self.code))
        self.image.save(f"{self.code}.png", content, save=False)
        self.save(update_fields=['image'])

    def __str__(self):
        if self.device:
            return f"QR {self.code} для {self.device.inventory_number}"
        return f"QR {self.code} (свободный)"


class Admin(Employee):
    class Meta:
        proxy = True
        verbose_name = 'Администратор'
        verbose_name_plural = 'Администраторы'

    def save(self, *args, **kwargs):
        self.is_admin = True
        super().save(*args, **kwargs)


class DeviceHistory(models.Model):
    device = models.ForeignKey(
        Device, on_delete=models.CASCADE, related_name='history',
        verbose_name="Устройство"
    )
    timestamp = models.DateTimeField("Время изменения", auto_now_add=True)
    field = models.CharField("Поле", max_length=50, choices=[
        ('responsible', 'Ответственный'),
        ('department', 'Отдел'),
        ('status', 'Статус'),
    ])
    old_value = models.TextField("Старое значение", blank=True, null=True)
    new_value = models.TextField("Новое значение", blank=True, null=True)

    class Meta:
        verbose_name = "История перемещения"
        verbose_name_plural = "История перемещений"
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.device} – {self.get_field_display()} изменён {self.timestamp.strftime('%d.%m.%Y %H:%M')}"


class QRPrintSettings(models.Model):
    TEXT_POSITION_CHOICES = [
        ('top', 'Сверху'),
        ('bottom', 'Снизу'),
        ('none', 'Скрыть текст'),
    ]

    card_width_mm = models.PositiveIntegerField("Ширина карточки (мм)", default=70)
    card_height_mm = models.PositiveIntegerField("Высота карточки (мм)", default=95)
    qr_size_px = models.PositiveIntegerField("Размер QR (px)", default=220)
    text_size_px = models.PositiveIntegerField("Размер текста (px)", default=13)
    text_position = models.CharField("Позиция текста", max_length=10, choices=TEXT_POSITION_CHOICES, default='bottom')

    class Meta:
        verbose_name = "Настройки печати QR"
        verbose_name_plural = "Настройки печати QR"

    def __str__(self):
        return "Настройки печати QR"


class MovementCard(models.Model):
    history = models.OneToOneField(
        DeviceHistory,
        on_delete=models.CASCADE,
        related_name='movement_card',
        verbose_name="История перемещения",
    )
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)

    class Meta:
        verbose_name = "Карточка перемещения"
        verbose_name_plural = "Карточки перемещения"
        ordering = ['-created_at']

    def __str__(self):
        return f"Карточка перемещения #{self.id} ({self.history.device.inventory_number})"

    @property
    def device(self):
        return self.history.device


class ImportAction(models.Model):
    """
    Виртуальная модель для отображения кастомного действия в админке.
    Не создаёт таблицу в БД.
    """
    class Meta:
        managed = False
        verbose_name = "Импорт из Excel"
        verbose_name_plural = "Импорт из Excel"