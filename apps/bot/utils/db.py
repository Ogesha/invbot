from asgiref.sync import sync_to_async
from django.apps import apps
from apps.core.models import Employee, Device, QRCode, RegistrationRequest, DeviceType, Department



def _region_filter_for_admin(telegram_id):
    admin_emp = Employee.objects.filter(telegram_id=telegram_id, is_admin=True, is_approved=True).first()
    if not admin_emp:
        return None

    try:
        admin_scope_model = apps.get_model('core', 'AdminScope')
    except LookupError:
        return None

    scope = admin_scope_model.objects.filter(employee=admin_emp).prefetch_related('allowed_regions').first()
    if not scope or scope.can_manage_all_regions:
        return None

    return list(scope.allowed_regions.values_list('id', flat=True))

# ---------- Базовые функции (используются в start.py и др.) ----------
@sync_to_async
def get_employee_by_telegram(telegram_id):
    try:
        return Employee.objects.select_related('department').get(telegram_id=telegram_id, is_approved=True)
    except Employee.DoesNotExist:
        return None

@sync_to_async
def get_device_by_qr_code(code):
    try:
        qr = QRCode.objects.select_related('device__responsible', 'device__department', 'device__device_type').get(code=code, is_active=True)
        return qr.device
    except QRCode.DoesNotExist:
        return None

@sync_to_async
def get_device_by_code_or_id(identifier):
    try:
        qr_id = int(identifier)
        qr = QRCode.objects.select_related('device__responsible', 'device__department', 'device__device_type').filter(id=qr_id, is_active=True).first()
        if qr:
            return qr.device
    except ValueError:
        pass
    try:
        qr = QRCode.objects.select_related('device__responsible', 'device__department', 'device__device_type').get(code=identifier, is_active=True)
        return qr.device
    except QRCode.DoesNotExist:
        return None

@sync_to_async
def get_employee_devices(employee):
    return list(employee.devices.select_related('device_type', 'department').all())

@sync_to_async
def get_all_devices_filtered(department_id=None, device_type_id=None, status=None, admin_telegram_id=None):
    qs = Device.objects.select_related('department', 'region', 'device_type', 'responsible').all()
    if admin_telegram_id is not None:
        region_ids = _region_filter_for_admin(admin_telegram_id)
        if region_ids is not None:
            qs = qs.filter(region_id__in=region_ids)
    if department_id and department_id != 'all':
        qs = qs.filter(department_id=department_id)
    if device_type_id and device_type_id != 'all':
        qs = qs.filter(device_type_id=device_type_id)
    if status is not None and status != 'all':
        qs = qs.filter(status=(status == 'active'))
    return list(qs)

@sync_to_async
def get_departments(admin_telegram_id=None):
    qs = Department.objects.all()
    if admin_telegram_id is not None:
        region_ids = _region_filter_for_admin(admin_telegram_id)
        if region_ids is not None:
            qs = qs.filter(region_id__in=region_ids)
    return list(qs)

@sync_to_async
def get_device_types():
    return list(DeviceType.objects.all())

@sync_to_async
def is_admin(telegram_id):
    return Employee.objects.filter(telegram_id=telegram_id, is_admin=True, is_approved=True).exists()

@sync_to_async
def create_registration_request(telegram_id, username, full_name):
    RegistrationRequest.objects.filter(telegram_id=telegram_id).delete()
    request = RegistrationRequest.objects.create(
        telegram_id=telegram_id,
        telegram_username=username,
        full_name=full_name
    )
    return request, True

@sync_to_async
def get_pending_registration_request(telegram_id):
    try:
        return RegistrationRequest.objects.get(telegram_id=telegram_id, is_processed=False)
    except RegistrationRequest.DoesNotExist:
        return None

# ---------- Функции для сотрудников ----------
@sync_to_async
def create_employee(full_name, department_id=None, is_approved=False, telegram_id=None, **kwargs):
    employee = Employee.objects.create(
        full_name=full_name,
        department_id=department_id,
        is_approved=is_approved,
        telegram_id=telegram_id,
        **kwargs
    )
    return employee

@sync_to_async
def get_all_employees():
    return list(Employee.objects.all().order_by('full_name'))

@sync_to_async
def get_all_employees_data(admin_telegram_id=None):
    qs = Employee.objects.select_related('department')
    if admin_telegram_id is not None:
        region_ids = _region_filter_for_admin(admin_telegram_id)
        if region_ids is not None:
            qs = qs.filter(department__region_id__in=region_ids)
    return list(qs.order_by('full_name').values('id', 'full_name', 'is_approved', 'department__name'))

@sync_to_async
def get_all_employees_with_dept(admin_telegram_id=None, department_id=None):
    qs = Employee.objects.select_related('department').all()
    if department_id is not None:
        qs = qs.filter(department_id=department_id)
    if admin_telegram_id is not None:
        region_ids = _region_filter_for_admin(admin_telegram_id)
        if region_ids is not None:
            qs = qs.filter(department__region_id__in=region_ids)
    return list(qs.order_by('full_name'))

@sync_to_async
def get_all_departments(admin_telegram_id=None):
    qs = Department.objects.all()
    if admin_telegram_id is not None:
        region_ids = _region_filter_for_admin(admin_telegram_id)
        if region_ids is not None:
            qs = qs.filter(region_id__in=region_ids)
    return list(qs)

@sync_to_async
def get_employees_by_department(department_id, admin_telegram_id=None):
    qs = Employee.objects.filter(department_id=department_id).select_related('department')
    if admin_telegram_id is not None:
        region_ids = _region_filter_for_admin(admin_telegram_id)
        if region_ids is not None:
            qs = qs.filter(department__region_id__in=region_ids)
    return list(qs.order_by('full_name'))

@sync_to_async
def get_employee_data(employee_id):
    try:
        return Employee.objects.select_related('department').get(id=employee_id)
    except Employee.DoesNotExist:
        return None

@sync_to_async
def get_employee_data_safe(employee_id):
    try:
        emp = Employee.objects.select_related('department').get(id=employee_id)
        return {
            'id': emp.id,
            'full_name': emp.full_name,
            'department_name': emp.department.name if emp.department else None,
            'is_approved': emp.is_approved,
            'telegram_id': emp.telegram_id,
        }
    except Employee.DoesNotExist:
        return None

@sync_to_async
def update_employee(employee_id, full_name=None, department_id=None, is_approved=None, telegram_id=...):
    try:
        emp = Employee.objects.get(id=employee_id)
        if full_name is not None:
            emp.full_name = full_name
        if department_id is not None:
            emp.department_id = department_id
        if is_approved is not None:
            emp.is_approved = is_approved
        if telegram_id is not ...:
            emp.telegram_id = telegram_id
        emp.save()
        return emp
    except Employee.DoesNotExist:
        return None

@sync_to_async
def delete_employee(employee_id):
    try:
        emp = Employee.objects.get(id=employee_id)
        emp.delete()
        return True
    except Employee.DoesNotExist:
        return False

@sync_to_async
def get_employee_devices(employee_id):
    try:
        emp = Employee.objects.get(id=employee_id)
        return list(emp.devices.select_related('device_type').all())
    except Employee.DoesNotExist:
        return []

# ---------- Функции для QR-кодов ----------
@sync_to_async
def create_qr_code(admin_telegram_id=None):
    qr = QRCode.objects.create(is_active=True)
    qr.generate_simple_image()
    qr.refresh_from_db(fields=['image'])
    return qr

@sync_to_async
def get_all_free_qr_codes():
    return list(QRCode.objects.filter(device__isnull=True, is_active=True).order_by('-created_at'))

@sync_to_async
def get_qr_by_id(qr_id):
    try:
        return QRCode.objects.get(id=qr_id)
    except QRCode.DoesNotExist:
        return None

@sync_to_async
def get_qr_data(qr_id):
    try:
        return QRCode.objects.select_related('device').get(id=qr_id)
    except QRCode.DoesNotExist:
        return None

@sync_to_async
def assign_qr_to_device(qr_id, device_id, admin_telegram_id=None):
    from apps.core.models import QRCode, Device
    try:
        qr = QRCode.objects.get(id=qr_id, is_active=True)
        device = Device.objects.get(id=device_id)
        if admin_telegram_id is not None:
            region_ids = _region_filter_for_admin(admin_telegram_id)
            if region_ids is not None and device.region_id and device.region_id not in region_ids:
                return False, 'Нет доступа к региону этой техники'

        # Разрешаем привязку только к свободной технике (без QR)
        try:
            existing_qr = device.qr_code
        except QRCode.DoesNotExist:
            existing_qr = None

        if existing_qr and existing_qr != qr:
            return False, f"Устройство {device.inventory_number} уже имеет QR-код (ID {existing_qr.id})"

        qr.device = device
        qr.save()
        qr.generate_image()
        return True, f"QR {qr.code} привязан к устройству {device.inventory_number}"
    except Exception as e:
        return False, str(e)

@sync_to_async
def get_all_devices(admin_telegram_id=None):
    from apps.core.models import Device
    qs = Device.objects.select_related('department', 'responsible').all()
    if admin_telegram_id is not None:
        region_ids = _region_filter_for_admin(admin_telegram_id)
        if region_ids is not None:
            qs = qs.filter(region_id__in=region_ids)
    return list(qs.order_by('inventory_number'))

@sync_to_async
def get_device_data(device_id, admin_telegram_id=None):
    qs = Device.objects.select_related('department', 'responsible', 'device_type')
    if admin_telegram_id is not None:
        region_ids = _region_filter_for_admin(admin_telegram_id)
        if region_ids is not None:
            qs = qs.filter(region_id__in=region_ids)
    try:
        return qs.get(id=device_id)
    except Device.DoesNotExist:
        return None

@sync_to_async
def change_device_responsible(device_id, new_responsible_id, admin_telegram_id=None):
    try:
        device = Device.objects.select_related('department', 'responsible').get(id=device_id)
        employee = Employee.objects.select_related('department').get(id=new_responsible_id)
    except (Device.DoesNotExist, Employee.DoesNotExist):
        return False, 'Устройство или сотрудник не найдены', None

    if admin_telegram_id is not None:
        region_ids = _region_filter_for_admin(admin_telegram_id)
        if region_ids is not None:
            dev_region = device.department.region_id if device.department else None
            emp_region = employee.department.region_id if employee.department else None
            if (dev_region and dev_region not in region_ids) or (emp_region and emp_region not in region_ids):
                return False, 'Нет доступа к выбранному региону', None

    old_responsible = device.responsible
    old_department = device.department

    device.responsible = employee
    if employee.department and employee.department != device.department:
        device.department = employee.department
    device.save()

    device.refresh_from_db(fields=['department', 'responsible'])
    from apps.core.models import MovementCard
    card = MovementCard.objects.filter(history__device=device, history__field='responsible').order_by('-created_at').first()
    movement_info = {
        'device': device,
        'from_department': old_department.name if old_department else '—',
        'to_department': device.department.name if device.department else '—',
        'from_responsible': old_responsible.full_name if old_responsible else '—',
        'to_responsible': device.responsible.full_name if device.responsible else '—',
        'card_id': card.id if card else None,
    }
    return True, 'Ответственный успешно изменён', movement_info

@sync_to_async
def get_devices_without_qr(admin_telegram_id=None):
    from apps.core.models import Device
    qs = Device.objects.filter(qr_code__isnull=True).select_related('department', 'region', 'responsible')
    if admin_telegram_id is not None:
        region_ids = _region_filter_for_admin(admin_telegram_id)
        if region_ids is not None:
            qs = qs.filter(region_id__in=region_ids)
    return list(qs.order_by('inventory_number'))

@sync_to_async
def get_all_qr_codes_with_pagination(page=1, page_size=10):
    from django.core.paginator import Paginator
    qs = QRCode.objects.select_related('device').order_by('-created_at')
    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page)
    return {
        'items': list(page_obj.object_list),
        'has_prev': page_obj.has_previous(),
        'has_next': page_obj.has_next(),
        'prev_page': page_obj.previous_page_number() if page_obj.has_previous() else None,
        'next_page': page_obj.next_page_number() if page_obj.has_next() else None,
        'total_pages': paginator.num_pages,
        'current_page': page,
    }

@sync_to_async
def get_all_qr_codes_data(page=1, page_size=10):
    from django.core.paginator import Paginator
    qs = QRCode.objects.select_related('device').order_by('-created_at')
    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page)
    items = []
    for qr in page_obj.object_list:
        items.append({
            'id': qr.id,
            'code': qr.code,
            'device_inventory': qr.device.inventory_number if qr.device else None,
            'is_active': qr.is_active,
            'created_at': qr.created_at,
        })
    return {
        'items': items,
        'has_prev': page_obj.has_previous(),
        'has_next': page_obj.has_next(),
        'prev_page': page_obj.previous_page_number() if page_obj.has_previous() else None,
        'next_page': page_obj.next_page_number() if page_obj.has_next() else None,
        'total_pages': paginator.num_pages,
        'current_page': page,
    }

@sync_to_async
def get_free_qr_codes_with_pagination(page=1, page_size=10):
    from django.core.paginator import Paginator
    qs = QRCode.objects.filter(device__isnull=True, is_active=True).select_related('device').order_by('-created_at')
    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page)
    return {
        'items': list(page_obj.object_list),
        'has_prev': page_obj.has_previous(),
        'has_next': page_obj.has_next(),
        'prev_page': page_obj.previous_page_number() if page_obj.has_previous() else None,
        'next_page': page_obj.next_page_number() if page_obj.has_next() else None,
        'total_pages': paginator.num_pages,
        'current_page': page,
    }

@sync_to_async
def get_free_qr_codes_data(page=1, page_size=10):
    from django.core.paginator import Paginator
    qs = QRCode.objects.filter(device__isnull=True, is_active=True).order_by('-created_at')
    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page)
    items = [{'id': qr.id, 'code': qr.code, 'created_at': qr.created_at} for qr in page_obj.object_list]
    return {
        'items': items,
        'has_prev': page_obj.has_previous(),
        'has_next': page_obj.has_next(),
        'prev_page': page_obj.previous_page_number() if page_obj.has_previous() else None,
        'next_page': page_obj.next_page_number() if page_obj.has_next() else None,
        'total_pages': paginator.num_pages,
        'current_page': page,
    }

@sync_to_async
def regenerate_qr_image(qr_id):
    try:
        qr = QRCode.objects.get(id=qr_id)
        qr.generate_simple_image()
        return True, f"Изображение для QR {qr.code} обновлено"
    except QRCode.DoesNotExist:
        return False, "QR-код не найден"
    except Exception as e:
        return False, str(e)

# ---------- Функции для заявок на регистрацию ----------
@sync_to_async
def get_all_pending_requests():
    from apps.core.models import RegistrationRequest
    return list(RegistrationRequest.objects.filter(is_processed=False).order_by('-created_at'))

@sync_to_async
def get_all_pending_requests_data():
    from apps.core.models import RegistrationRequest
    return list(RegistrationRequest.objects.filter(is_processed=False).order_by('-created_at').values('id', 'full_name', 'telegram_username', 'telegram_id', 'created_at'))

@sync_to_async
def approve_request(request_id):
    from apps.core.models import RegistrationRequest, Employee
    try:
        req = RegistrationRequest.objects.get(id=request_id, is_processed=False)
        Employee.objects.create(
            full_name=req.full_name,
            telegram_id=req.telegram_id,
            is_approved=True
        )
        req.is_processed = True
        req.approved = True
        req.save()
        return True, req
    except Exception as e:
        return False, str(e)

@sync_to_async
def reject_request(request_id, comment=""):
    from apps.core.models import RegistrationRequest
    try:
        req = RegistrationRequest.objects.get(id=request_id, is_processed=False)
        req.is_processed = True
        req.approved = False
        req.comment = comment
        req.save()
        return True, req
    except Exception as e:
        return False, str(e)



@sync_to_async
def create_device(inventory_number, name, device_type_id, department_id=None, responsible_id=None, status='in_use', admin_telegram_id=None):
    if Device.objects.filter(inventory_number=inventory_number).exists():
        return False, 'Техника с таким инвентарным номером уже существует'

    region_id = None
    if department_id:
        dept = Department.objects.filter(id=department_id).select_related('region').first()
        if not dept:
            return False, 'Отдел не найден'
        region_id = dept.region_id

    if admin_telegram_id is not None:
        region_ids = _region_filter_for_admin(admin_telegram_id)
        if region_ids is not None and region_id and region_id not in region_ids:
            return False, 'Нет доступа к выбранному региону'

    device = Device.objects.create(
        inventory_number=inventory_number,
        name=name,
        device_type_id=device_type_id,
        department_id=department_id,
        responsible_id=responsible_id,
        status=status,
        region_id=region_id,
    )
    return True, device


@sync_to_async
def update_device_status(device_id, status, admin_telegram_id=None):
    if status not in {'in_use', 'not_in_use', 'reserve'}:
        return False, 'Некорректный статус'

    qs = Device.objects.all()
    if admin_telegram_id is not None:
        region_ids = _region_filter_for_admin(admin_telegram_id)
        if region_ids is not None:
            qs = qs.filter(region_id__in=region_ids)

    device = qs.filter(id=device_id).first()
    if not device:
        return False, 'Техника не найдена или нет доступа'

    device.status = status
    device.save(update_fields=['status'])
    return True, f'Статус обновлён: {device.inventory_number} — {device.get_status_display()}'


@sync_to_async
def delete_device(device_id, admin_telegram_id=None):
    qs = Device.objects.all()
    if admin_telegram_id is not None:
        region_ids = _region_filter_for_admin(admin_telegram_id)
        if region_ids is not None:
            qs = qs.filter(region_id__in=region_ids)

    device = qs.filter(id=device_id).first()
    if not device:
        return False, 'Техника не найдена или нет доступа'

    inv = device.inventory_number
    name = device.name
    device.delete()
    return True, f'Удалена техника: {inv} — {name}'

@sync_to_async
def create_device_with_qr(code, name, inventory_number, device_type_id, department_id=None, responsible_id=None):
    region_id = None
    if department_id:
        dept = Department.objects.filter(id=department_id).select_related('region').first()
        region_id = dept.region_id if dept else None
    device = Device.objects.create(
        name=name,
        inventory_number=inventory_number,
        device_type_id=device_type_id,
        department_id=department_id,
        region_id=region_id,
        responsible_id=responsible_id,
        status='in_use'
    )
    QRCode.objects.create(device=device, code=code, is_active=True)
    return device

@sync_to_async
def send_movement_card_to_print(card_id, admin_telegram_id):
    import requests
    from requests.exceptions import SSLError
    admin_emp = Employee.objects.filter(telegram_id=admin_telegram_id, is_admin=True, is_approved=True).first()
    if not admin_emp:
        return False, 'Администратор не найден'

    try:
        admin_scope_model = apps.get_model('core', 'AdminScope')
    except LookupError:
        return False, 'Модель прав администратора недоступна'

    scope = admin_scope_model.objects.filter(employee=admin_emp).first()
    if not scope or not scope.can_print_from_bot:
        return False, 'Печать из бота отключена в настройках Django'
    if scope.printer_backend != 'http' or not scope.printer_endpoint:
        return False, 'Не настроен endpoint принтера'

    try:
        endpoint = scope.printer_endpoint
        if 'movement-card/print' not in endpoint:
            endpoint = endpoint.rstrip('/') + '/api/movement-card/print/'

        payload = {'movement_card_id': card_id}
        try:
            response = requests.post(endpoint, json=payload, timeout=7)
        except SSLError:
            # Локальные принт-серверы часто работают с self-signed сертификатами.
            # Повторяем запрос без валидации SSL только для внутреннего endpoint.
            requests.packages.urllib3.disable_warnings()  # type: ignore[attr-defined]
            response = requests.post(endpoint, json=payload, timeout=7, verify=False)

        if response.status_code >= 400:
            return False, f'Ошибка принтера: HTTP {response.status_code}'
        return True, 'Карточка отправлена на печать'
    except Exception as exc:
        return False, f'Ошибка отправки на печать: {exc}'
