import asyncio
from django.contrib import admin
from django.contrib.auth.models import Group
from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.html import format_html
from ..models import Department, Employee, RegistrationRequest, Admin, ImportAction, MovementCard, QRPrintSettings, MovementCardPrintSettings
from ...bot.notifications import send_message_sync
from ..utils import export_queryset_to_excel

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


class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'description', 'employee_count')
    search_fields = ('name',)
    actions = ['export_to_excel']
    inlines = [EmployeeInline]

    def employee_count(self, obj):
        count = obj.employees.count()
        # Используем правильный URL для прокси-модели EmployeeProxy в приложении staff
        url = reverse('admin:staff_employeeproxy_changelist') + f'?department__id__exact={obj.id}'
        return format_html('<a href="{}">{} сотрудников</a>', url, count)
    employee_count.short_description = "Сотрудники"

    def export_to_excel(self, request, queryset):
        fields = ['id', 'name', 'description']
        headers = ['ID', 'Название', 'Описание']
        return export_queryset_to_excel(queryset, 'departments', fields, headers)
    export_to_excel.short_description = "Экспортировать отделы в Excel"


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('id', 'full_name', 'department', 'telegram_id', 'is_admin', 'is_approved')
    list_filter = ('department', 'is_admin', 'is_approved')
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
        return super().get_queryset(request).filter(is_admin=True)

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


@admin.register(MovementCard)
class MovementCardAdmin(admin.ModelAdmin):
    list_display = ('id', 'device_inventory', 'device_name', 'from_department', 'to_department', 'from_responsible', 'to_responsible', 'created_at')
    list_filter = ('history__device__department', 'created_at')
    search_fields = ('history__device__inventory_number', 'history__device__name', 'history__old_value', 'history__new_value')
    actions = ['print_cards']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('history__device__department', 'history__device__responsible')

    def device_inventory(self, obj):
        return obj.history.device.inventory_number

    def device_name(self, obj):
        return obj.history.device.name

    def from_department(self, obj):
        return obj.from_department or '—'

    def to_department(self, obj):
        return obj.to_department or '—'

    def from_responsible(self, obj):
        return obj.from_responsible or '—'

    def to_responsible(self, obj):
        return obj.to_responsible or '—'

    def print_cards(self, request, queryset):
        settings_obj, _ = MovementCardPrintSettings.objects.get_or_create(pk=1)
        items = []
        for card in queryset.select_related('history__device__department', 'history__device__responsible'):
            device = card.history.device
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

