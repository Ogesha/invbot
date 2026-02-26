from django.contrib import admin
from django.utils.html import format_html
from ..models import QRCode, DeviceHistory

class QRCodeInline(admin.StackedInline):
    model = QRCode
    can_delete = False
    readonly_fields = ('image_preview',)
    fields = ('code', 'is_active', 'image', 'image_preview')

    def image_preview(self, obj):
        if obj and obj.image:
            return format_html('<img src="{}" width="100" height="100" style="object-fit: cover;" />', obj.image.url)
        return "Нет изображения"
    image_preview.short_description = "Превью"

class DeviceHistoryInline(admin.TabularInline):
    model = DeviceHistory
    extra = 0
    readonly_fields = ('field', 'old_value', 'new_value', 'timestamp')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False