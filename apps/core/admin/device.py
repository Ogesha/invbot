import os
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.contrib import messages
from django.shortcuts import redirect, render
from django import forms
from django.core.exceptions import ValidationError
from django.core.files import File
from django.db import models
from ..models import Device, DeviceType, QRCode, Computer, Printer, Employee, QRPrintSettings
from ..utils import export_queryset_to_excel, export_qrcodes_with_images_to_excel
from ...qr_generator.utils import generate_qr_image_for_device
from .inlines import QRCodeInline, DeviceHistoryInline
from django.db.models import OuterRef, Exists
from .scope import filter_by_scope


# ---------- Кастомная форма с валидацией ----------
class DeviceAdminForm(forms.ModelForm):
    class Meta:
        model = Device
        fields = '__all__'
        widgets = {
            'purchase_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'placeholder': 'ГГГГ-ММ-ДД'}),
        }

    def clean_purchase_date(self):
        value = self.cleaned_data.get('purchase_date')
        if value == '':
            return None
        return value

    def clean_department(self):
        value = self.cleaned_data.get('department')
        if value == '' or value is None:
            return None
        return value

    def clean_responsible(self):
        value = self.cleaned_data.get('responsible')
        if value == '' or value is None:
            return None
        return value

    def clean(self):
        cleaned_data = super().clean()
        department = cleaned_data.get('department')
        responsible = cleaned_data.get('responsible')

        if responsible and department:
            if responsible.department != department:
                raise ValidationError(
                    f"Сотрудник {responsible.full_name} не принадлежит отделу {department.name}. "
                    f"Пожалуйста, выберите сотрудника из этого отдела."
                )
        return cleaned_data


# ---------- Скрытая регистрация Device ----------
class DeviceAdminHidden(admin.ModelAdmin):
    list_display = ('id', 'inventory_number', 'name')
    search_fields = ('inventory_number', 'name')

    def get_model_perms(self, request):
        return {}


admin.site.register(Device, DeviceAdminHidden)


# ---------- Базовый класс для всех устройств ----------
class BaseDeviceAdmin(admin.ModelAdmin):
    form = DeviceAdminForm
    list_display = ('id', 'inventory_number', 'name', 'department', 'responsible', 'status_display', 'qr_code_link')
    list_filter = ('department', 'status', 'responsible')
    search_fields = ('inventory_number', 'name', 'serial_number')
    inlines = [QRCodeInline, DeviceHistoryInline]
    actions = ['generate_qr_codes', 'print_qr_codes', 'export_to_excel', 'generate_qr_codes_with_path']

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related('qr_code', 'department')
        return filter_by_scope(qs, request.user, region_path='department__region')

    def qr_code_link(self, obj):
        try:
            qr = obj.qr_code
        except QRCode.DoesNotExist:
            qr = None

        if qr:
            return format_html('<b>ID: {}</b><br><span style="font-size:11px;">{}</span>', qr.id, qr.code)
        return "—"
    qr_code_link.short_description = "QR-код"

    def status_display(self, obj):
        return obj.get_status_display()
    status_display.short_description = "Статус"

    def generate_qr_codes(self, request, queryset):
        generated = 0
        reused = 0
        errors = 0

        for device in queryset:
            try:
                qr, created = QRCode.objects.get_or_create(device=device)

                if not created and qr.image:
                    reused += 1
                    continue

                filepath = generate_qr_image_for_device(device)
                if filepath and os.path.exists(filepath):
                    with open(filepath, 'rb') as f:
                        qr.image.save(os.path.basename(filepath), File(f), save=False)
                    qr.save(update_fields=['image'])
                    generated += 1
                else:
                    errors += 1
            except Exception:
                errors += 1

        level = messages.SUCCESS if errors == 0 else messages.WARNING
        self.message_user(
            request,
            f"Сгенерировано новых QR: {generated}. Уже были готовы: {reused}. Ошибок: {errors}.",
            level=level,
        )
        return redirect(request.get_full_path())
    generate_qr_codes.short_description = "Сгенерировать QR-коды"

    def print_qr_codes(self, request, queryset):
        items = []
        for device in queryset.select_related('device_type'):
            qr, _ = QRCode.objects.get_or_create(device=device)
            if not qr.image:
                qr.generate_image()
                qr.refresh_from_db(fields=['image'])

            items.append({
                'device': device,
                'qr': qr,
                'image_url': qr.image.url if qr.image else None,
            })

        settings_obj, _ = QRPrintSettings.objects.get_or_create(pk=1)
        context = {
            'title': 'Печать QR-кодов',
            'items': items,
            'opts': self.model._meta,
            'print_settings': settings_obj,
            'settings_url': reverse('admin:core_qrprintsettings_change', args=[settings_obj.id]),
        }
        return render(request, 'admin/print_qr_codes.html', context)
    print_qr_codes.short_description = "Печать QR-кодов"

    def export_to_excel(self, request, queryset):
        fields = [
            'inventory_number',
            'name',
            'department__name',
            'responsible__full_name',
            'status',
            'serial_number',
            'manufacturer',
            'description',
        ]
        headers = [
            'Инвентарный номер',
            'Наименование',
            'Отдел',
            'Ответственный',
            'Статус',
            'Серийный номер',
            'Производитель',
            'Описание',
        ]
        if queryset.model is Computer:
            fields.extend(['processor', 'ram', 'disk_size'])
            headers.extend(['Процессор', 'ОЗУ', 'Диск'])
        elif queryset.model is Printer:
            fields.extend(['color_type', 'paper_format'])
            headers.extend(['Тип печати', 'Формат'])
        return export_queryset_to_excel(queryset, 'devices', fields, headers)
    export_to_excel.short_description = "Экспортировать выбранные записи в Excel"

    def generate_qr_codes_with_path(self, request, queryset):
        ids = ','.join(str(obj.id) for obj in queryset)
        return redirect(f"{reverse('generate_qr_with_path')}?ids={ids}")
    generate_qr_codes_with_path.short_description = "Сгенерировать QR-коды с выбором папки"

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        try:
            department_id = None
            if request.method == 'POST':
                dept_param = request.POST.get('department')
                if dept_param and dept_param.isdigit():
                    department_id = int(dept_param)
                    print(f"POST department_id = {department_id}")
            elif obj and obj.department:
                department_id = obj.department.id
                print(f"GET department_id from obj = {department_id}")

            base_qs = filter_by_scope(Employee.objects.filter(is_approved=True), request.user, region_path='department__region')
            if department_id:
                form.base_fields['responsible'].queryset = base_qs.filter(
                    department_id=department_id
                ).order_by('full_name')
            else:
                form.base_fields['responsible'].queryset = base_qs.order_by('full_name')
        except Exception as e:
            print(f"Ошибка в get_form: {e}")
            import traceback
            traceback.print_exc()
            form.base_fields['responsible'].queryset = filter_by_scope(Employee.objects.filter(is_approved=True), request.user, region_path='department__region').order_by('full_name')
        return form

    def get_actions(self, request):
        actions = super().get_actions(request)
        print(f"get_actions для {self.__class__.__name__}: {list(actions.keys())}")
        return actions


# ---------- Админка для компьютеров (не регистрируется здесь) ----------
class ComputerAdmin(BaseDeviceAdmin):
    actions = BaseDeviceAdmin.actions
    list_display = BaseDeviceAdmin.list_display + ('processor', 'ram', 'disk_size')
    fieldsets = (
        (None, {'fields': ('inventory_number', 'name', 'description')}),
        ('Характеристики компьютера', {'fields': ('processor', 'ram', 'disk_size')}),
        ('Расположение', {'fields': ('department', 'responsible', 'status')}),
        ('Дополнительно', {'fields': ('serial_number', 'manufacturer', 'photo', 'purchase_date')}),
    )

    def save_model(self, request, obj, form, change):
        from ..models import DeviceType
        obj.device_type, _ = DeviceType.objects.get_or_create(name='Компьютер', code='PC')
        super().save_model(request, obj, form, change)


# ---------- Админка для принтеров (не регистрируется здесь) ----------
class PrinterAdmin(BaseDeviceAdmin):
    list_display = BaseDeviceAdmin.list_display + ('color_type', 'paper_format')
    fieldsets = (
        (None, {'fields': ('inventory_number', 'name', 'description')}),
        ('Характеристики принтера', {'fields': ('color_type', 'paper_format')}),
        ('Расположение', {'fields': ('department', 'responsible', 'status')}),
        ('Дополнительно', {'fields': ('serial_number', 'manufacturer', 'photo', 'purchase_date')}),
    )

    def save_model(self, request, obj, form, change):
        from ..models import DeviceType
        obj.device_type, _ = DeviceType.objects.get_or_create(name='Принтер', code='PRN')
        super().save_model(request, obj, form, change)


# ---------- Админка для QR-кодов ----------
@admin.register(QRCode)
class QRCodeAdmin(admin.ModelAdmin):
    list_display = ('id', 'code', 'device', 'created_at', 'is_active', 'image_preview')
    list_filter = ('is_active', 'created_at', 'device__department')
    search_fields = ('code', 'device__inventory_number')
    readonly_fields = ('id', 'image_preview_detail', 'device_short_info')
    autocomplete_fields = ['device']
    actions = [
        'deactivate_qr', 'activate_qr', 'regenerate_image',
        'export_to_excel', 'export_to_excel_with_images',
        'assign_to_device'
    ]

    fieldsets = (
        (None, {'fields': ('id', 'code', 'device', 'is_active', 'device_short_info')}),
        ('Изображение', {'fields': ('image', 'image_preview_detail'), 'classes': ('wide',)}),
    )


    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related('device__department')
        return filter_by_scope(qs, request.user, region_path='device__department__region')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'device':
            subquery = QRCode.objects.filter(device=OuterRef('pk'))
            free_devices = filter_by_scope(Device.objects.annotate(has_qr=Exists(subquery)).filter(has_qr=False), request.user, region_path='department__region')

            obj_id = request.resolver_match.kwargs.get('object_id') if request.resolver_match else None
            if obj_id:
                try:
                    qr = self.get_queryset(request).get(pk=obj_id)
                    kwargs['queryset'] = filter_by_scope(
                        Device.objects.annotate(has_qr=Exists(subquery)).filter(models.Q(has_qr=False) | models.Q(pk=qr.device_id)),
                        request.user,
                        region_path='department__region'
                    ).order_by('inventory_number')
                except QRCode.DoesNotExist:
                    kwargs['queryset'] = free_devices.order_by('inventory_number')
            else:
                kwargs['queryset'] = free_devices.order_by('inventory_number')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="50" height="50" style="object-fit: cover;" />', obj.image.url)
        return "—"
    image_preview.short_description = "Превью"

    def image_preview_detail(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-width: 100%; max-height: 300px;" />', obj.image.url)
        return "Изображение не сгенерировано"
    image_preview_detail.short_description = "Предпросмотр"

    def device_short_info(self, obj):
        if obj.device:
            return format_html(
                "ID QR: {}<br>Устройство: {}<br>Инв. №: {}",
                obj.id,
                obj.device.name,
                obj.device.inventory_number,
            )
        return "—"
    device_short_info.short_description = "Информация об устройстве"

    def deactivate_qr(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f"Деактивировано {queryset.count()} QR-кодов.")
    deactivate_qr.short_description = "Деактивировать выбранные QR-коды"

    def activate_qr(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f"Активировано {queryset.count()} QR-кодов.")
    activate_qr.short_description = "Активировать выбранные QR-коды"

    def regenerate_image(self, request, queryset):
        regenerated = 0
        for qr in queryset:
            if qr.device:
                qr.generate_image()
            else:
                qr.generate_simple_image()
            regenerated += 1
        self.message_user(request, f"Изображения обновлены для {regenerated} QR-кодов.")
    regenerate_image.short_description = "Перегенерировать изображения"

    def export_to_excel(self, request, queryset):
        fields = ['code', 'device__inventory_number', 'device__name', 'created_at', 'is_active']
        headers = ['Код QR', 'Инв. номер', 'Название', 'Дата', 'Активен']
        return export_queryset_to_excel(queryset, 'qrcodes', fields, headers)
    export_to_excel.short_description = "Экспортировать в Excel (текст)"

    def export_to_excel_with_images(self, request, queryset):
        qs = queryset.select_related('device')
        return export_qrcodes_with_images_to_excel(qs, 'qrcodes_with_images')
    export_to_excel_with_images.short_description = "Экспортировать в Excel с изображениями"

    def assign_to_device(self, request, queryset):
        ids = ','.join(str(obj.id) for obj in queryset)
        return redirect(f"{reverse('assign_qr_to_device')}?qr_ids={ids}")
    assign_to_device.short_description = "Привязать QR-коды к устройству"