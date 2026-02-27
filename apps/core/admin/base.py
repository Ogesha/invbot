import asyncio
from django.contrib import admin
from django.contrib.auth.models import Group
from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.html import format_html
from django import forms
from ..models import Department, Employee, RegistrationRequest, Admin, ImportAction, MovementCard, QRPrintSettings, MovementCardPrintSettings, Region, AdminScope
from ...bot.notifications import send_message_sync
from ..utils import export_queryset_to_excel
from .scope import filter_by_scope

admin.site.unregister(Group)


class EmployeeInline(admin.TabularInline):
    model = Employee
    fields = ('id', 'full_name', 'is_admin', 'is_approved')
    readonly_fields = ('id',)
    extra = 0
    can_delete = False
    verbose_name = "Сотрудник"
    verbose_name_plural = "Сотрудники отдела"

    def has_add_permission(self, request, obj=None):
        return False




class DepartmentLookupAdmin(admin.ModelAdmin):
    search_fields = ('name',)

    def get_model_perms(self, request):
        return {}


admin.site.register(Department, DepartmentLookupAdmin)


class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'region', 'description', 'employee_count')
    search_fields = ('name',)
    list_filter = ('region',)
    actions = ['export_to_excel']
    inlines = [EmployeeInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return filter_by_scope(qs, request.user)

    def employee_count(self, obj):
        count = obj.employees.count()
        # Используем правильный URL для прокси-модели EmployeeProxy в приложении staff
        url = reverse('admin:staff_employeeproxy_changelist') + f'?department__id__exact={obj.id}'
        return format_html('<a href="{}">{} сотрудников</a>', url, count)
    employee_count.short_description = "Сотрудники"

    def export_to_excel(self, request, queryset):
        fields = ['id', 'name', 'region__name', 'description']
        headers = ['ID', 'Название', 'Регион', 'Описание']
        return export_queryset_to_excel(queryset, 'departments', fields, headers)
    export_to_excel.short_description = "Экспортировать отделы в Excel"


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('id', 'full_name', 'department', 'employee_region', 'telegram_id', 'is_admin', 'is_approved')
    list_filter = ('department__region', 'department', 'is_admin', 'is_approved')
    search_fields = ('full_name', 'telegram_id')
    list_editable = ('is_admin',)
    actions = ['approve_selected', 'make_admin', 'remove_admin', 'export_to_excel']
    # Убираем telegram_id из exclude, чтобы он отображался
    exclude = ('email', 'phone', 'position')  # только email, phone, position скрыты

    fieldsets = (
        (None, {
            'fields': ('full_name', 'department', 'telegram_id')  # добавили telegram_id
        }),
        ('Права', {
            'fields': ('is_admin', 'is_approved'),
            'classes': ('wide',),
            'description': 'Отметьте, если сотрудник является администратором системы (доступ к командам /list и созданию техники в боте).'
        }),
    )


    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return filter_by_scope(qs, request.user, region_path='department__region')

    def employee_region(self, obj):
        return obj.department.region.name if obj.department and obj.department.region else '—'


    def get_list_editable(self, request):
        if request.user.is_superuser:
            return self.list_editable
        return ()

    def get_actions(self, request):
        actions = super().get_actions(request)
        if not request.user.is_superuser:
            actions.pop('make_admin', None)
            actions.pop('remove_admin', None)
        return actions

    def approve_selected(self, request, queryset):
        queryset.update(is_approved=True)
        self.message_user(request, f"Отмеченные сотрудники подтверждены.")
    approve_selected.short_description = "Подтвердить выбранных сотрудников"

    def make_admin(self, request, queryset):
        queryset.update(is_admin=True)
        self.message_user(request, f"Выбранные сотрудники назначены администраторами.")
    make_admin.short_description = "Назначить администраторами"

    def remove_admin(self, request, queryset):
        queryset.update(is_admin=False)
        self.message_user(request, f"У выбранных сотрудников сняты права администратора.")
    remove_admin.short_description = "Снять права администратора"

    def export_to_excel(self, request, queryset):
        fields = [
            'id',
            'full_name',
            'department__name',
            'is_admin',
            'is_approved',
        ]
        headers = [
            'ID',
            'ФИО',
            'Отдел',
            'Администратор',
            'Подтверждён',
        ]
        return export_queryset_to_excel(queryset, 'employees', fields, headers)
    export_to_excel.short_description = "Экспортировать выбранных сотрудников в Excel"


@admin.register(Admin)
class AdminAdmin(admin.ModelAdmin):
    list_display = ('id', 'full_name', 'department', 'is_approved')
    list_filter = ('department', 'is_approved')
    search_fields = ('full_name',)
    actions = ['approve_selected', 'export_to_excel']
    exclude = ('telegram_id', 'email', 'phone', 'is_admin', 'position')

    fieldsets = (
        (None, {
            'fields': ('full_name', 'department')
        }),
        ('Права', {
            'fields': ('is_approved',),
            'classes': ('wide',),
            'description': 'Администраторы имеют доступ к командам /list и созданию техники в боте.'
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request).filter(is_admin=True)
        return filter_by_scope(qs, request.user, region_path='department__region')

    def approve_selected(self, request, queryset):
        queryset.update(is_approved=True)
        self.message_user(request, f"Отмеченные администраторы подтверждены.")
    approve_selected.short_description = "Подтвердить выбранных администраторов"

    def export_to_excel(self, request, queryset):
        fields = [
            'id',
            'full_name',
            'department__name',
            'is_approved',
        ]
        headers = [
            'ID',
            'ФИО',
            'Отдел',
            'Подтверждён',
        ]
        return export_queryset_to_excel(queryset, 'admins', fields, headers)
    export_to_excel.short_description = "Экспортировать выбранных администраторов в Excel"

    def save_model(self, request, obj, form, change):
        obj.is_admin = True
        super().save_model(request, obj, form, change)


class RegistrationRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'full_name', 'created_at', 'is_processed', 'approved')
    list_filter = ('is_processed', 'approved', 'created_at')
    search_fields = ('full_name',)
    actions = ['approve_request', 'reject_request', 'export_to_excel']
    readonly_fields = ('created_at',)
    fields = ('full_name', 'created_at', 'comment')

    def approve_request(self, request, queryset):
        count = 0
        errors = 0
        for req in queryset.filter(is_processed=False):
            Employee.objects.create(
                full_name=req.full_name,
                telegram_id=req.telegram_id,
                is_approved=True
            )
            success = send_message_sync(
                req.telegram_id,
                f"✅ Ваша заявка на регистрацию одобрена! Добро пожаловать, {req.full_name}.\n"
                f"Теперь вы можете пользоваться ботом. Напишите /start для начала работы."
            )
            if not success:
                errors += 1
            req.delete()
            count += 1
        if errors:
            self.message_user(
                request,
                f"✅ Одобрено {count} заявок, но {errors} уведомлений не отправлено.",
                level=messages.WARNING
            )
        else:
            self.message_user(request, f"✅ Одобрено {count} заявок, уведомления отправлены.")
    approve_request.short_description = "Одобрить и удалить заявки"

    def reject_request(self, request, queryset):
        count = 0
        errors = 0
        for req in queryset:
            text = f"❌ Ваша заявка на регистрацию отклонена."
            if req.comment:
                text += f"\nКомментарий: {req.comment}"
            success = send_message_sync(req.telegram_id, text)
            if not success:
                errors += 1
            req.delete()
            count += 1
        if errors:
            self.message_user(
                request,
                f"❌ Отклонено {count} заявок, но {errors} уведомлений не отправлено.",
                level=messages.WARNING
            )
        else:
            self.message_user(request, f"❌ Отклонено {count} заявок, уведомления отправлены.")
    reject_request.short_description = "Отклонить и удалить заявки"

    def export_to_excel(self, request, queryset):
        fields = [
            'id',
            'full_name',
            'created_at',
            'is_processed',
            'approved',
            'comment',
        ]
        headers = [
            'ID',
            'ФИО',
            'Дата заявки',
            'Обработано',
            'Одобрено',
            'Комментарий',
        ]
        return export_queryset_to_excel(queryset, 'registration_requests', fields, headers)
    export_to_excel.short_description = "Экспортировать заявки в Excel"


class ImportActionAdmin(admin.ModelAdmin):
    def changelist_view(self, request, extra_context=None):
        return redirect('import_devices')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

admin.site.register(ImportAction, ImportActionAdmin)

@admin.register(QRPrintSettings)
class QRPrintSettingsAdmin(admin.ModelAdmin):
    list_display = ('id', 'card_width_mm', 'card_height_mm', 'qr_size_px', 'text_size_px', 'text_position')

    def has_add_permission(self, request):
        return not QRPrintSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False




@admin.register(MovementCardPrintSettings)
class MovementCardPrintSettingsAdmin(admin.ModelAdmin):
    list_display = ('id', 'card_width_mm', 'card_height_mm', 'text_size_px', 'title_size_px')

    def has_add_permission(self, request):
        return not MovementCardPrintSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)

    def has_module_permission(self, request):
        return request.user.is_superuser


@admin.register(AdminScope)
class AdminScopeAdmin(admin.ModelAdmin):
    list_display = ('id', 'django_user', 'employee', 'can_manage_all_regions', 'can_manage_devices', 'can_manage_employees', 'can_manage_qr', 'can_manage_movements', 'can_print_from_bot')
    filter_horizontal = ('allowed_regions',)

    def has_module_permission(self, request):
        return request.user.is_superuser


class MovementCardCreateForm(forms.ModelForm):
    class Meta:
        model = MovementCard
        fields = '__all__'

    def clean(self):
        cleaned = super().clean()
        dept = cleaned.get('to_department_obj')
        resp = cleaned.get('to_responsible_obj')
        if resp and dept and resp.department_id != dept.id:
            raise forms.ValidationError('Сотрудник должен принадлежать выбранному отделу.')
        return cleaned


@admin.register(MovementCard)
class MovementCardAdmin(admin.ModelAdmin):
    form = MovementCardCreateForm
    list_display = ('id', 'device_inventory', 'device_name', 'from_department', 'to_department', 'from_responsible', 'to_responsible', 'created_at')
    autocomplete_fields = ('device', 'to_department_obj', 'to_responsible_obj')
    search_fields = ('device__inventory_number', 'device__name', 'from_department', 'to_department', 'from_responsible', 'to_responsible')
    list_filter = ('history__device__department', 'created_at')
    actions = ['print_cards']

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related('device__department', 'device__responsible', 'history__device__department')
        return filter_by_scope(qs, request.user, region_path='device__department__region')

    def device_inventory(self, obj):
        dev = obj.device or (obj.history.device if obj.history else None)
        return dev.inventory_number if dev else '—'

    def device_name(self, obj):
        dev = obj.device or (obj.history.device if obj.history else None)
        return dev.name if dev else '—'

    def from_department(self, obj):
        return obj.from_department or '—'

    def to_department(self, obj):
        return obj.to_department or '—'

    def from_responsible(self, obj):
        return obj.from_responsible or '—'

    def to_responsible(self, obj):
        return obj.to_responsible or '—'



    fieldsets = (
        (None, {'fields': ('device', 'to_department_obj', 'to_responsible_obj')}),
        ('История', {'fields': ('history', 'from_department', 'to_department', 'from_responsible', 'to_responsible', 'created_at')}),
    )
    readonly_fields = ('history', 'from_department', 'to_department', 'from_responsible', 'to_responsible', 'created_at')

    def save_model(self, request, obj, form, change):
        from apps.core.models import DeviceHistory
        if not change and obj.device and obj.to_responsible_obj:
            old_dept = obj.device.department
            old_resp = obj.device.responsible

            new_dept = obj.to_department_obj or obj.to_responsible_obj.department
            obj.from_department = old_dept.name if old_dept else '—'
            obj.from_responsible = old_resp.full_name if old_resp else '—'
            obj.to_department = new_dept.name if new_dept else '—'
            obj.to_responsible = obj.to_responsible_obj.full_name if obj.to_responsible_obj else '—'

            history = DeviceHistory.objects.create(
                device=obj.device,
                field='responsible',
                old_value=obj.from_responsible,
                new_value=obj.to_responsible,
            )
            obj.history = history

            device_region = new_dept.region if new_dept else obj.device.region
            from apps.core.models import Device
            Device.objects.filter(pk=obj.device_id).update(
                responsible=obj.to_responsible_obj,
                department=new_dept,
                region=device_region,
            )

        super().save_model(request, obj, form, change)
    def print_cards(self, request, queryset):
        settings_obj, _ = MovementCardPrintSettings.objects.get_or_create(pk=1)
        items = []
        for card in queryset.select_related('device__department', 'device__responsible', 'history__device__department'):
            device = card.device or (card.history.device if card.history else None)
            dep_from = self.from_department(card)
            dep_to = self.to_department(card)
            items.append({
                'card': card,
                'device': device,
                'from_department': dep_from,
                'to_department': dep_to,
                'from_responsible': card.from_responsible or '—',
                'to_responsible': card.to_responsible or '—',
            })

        return render(
            request,
            'admin/print_movement_cards.html',
            {
                'title': 'Печать карточек перемещения',
                'items': items,
                'print_settings': settings_obj,
                'settings_url': reverse('admin:core_movementcardprintsettings_change', args=[settings_obj.id]),
            },
        )

    print_cards.short_description = 'Печать карточек перемещения'

