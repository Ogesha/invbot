from asgiref.sync import sync_to_async
from apps.core.models import Employee, Device, QRCode, RegistrationRequest, DeviceType, Department

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
def get_all_devices_filtered(department_id=None, device_type_id=None, status=None):
    qs = Device.objects.select_related('department', 'device_type', 'responsible').all()
    if department_id and department_id != 'all':
        qs = qs.filter(department_id=department_id)
    if device_type_id and device_type_id != 'all':
        qs = qs.filter(device_type_id=device_type_id)
    if status is not None and status != 'all':
        qs = qs.filter(status=(status == 'active'))
    return list(qs)

@sync_to_async
def get_departments():
    return list(Department.objects.all())

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
def get_all_employees_data():
    return list(
        Employee.objects.select_related('department')
        .order_by('full_name')
        .values('id', 'full_name', 'is_approved', 'department__name')
    )

@sync_to_async
def get_all_employees_with_dept():
    return list(Employee.objects.select_related('department').all().order_by('full_name'))

@sync_to_async
def get_all_departments():
    return list(Department.objects.all())

@sync_to_async
def get_employees_by_department(department_id):
    return list(Employee.objects.filter(department_id=department_id).select_related('department').order_by('full_name'))

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
        }
    except Employee.DoesNotExist:
        return None

@sync_to_async
def update_employee(employee_id, full_name=None, department_id=None, is_approved=None):
    try:
        emp = Employee.objects.get(id=employee_id)
        if full_name is not None:
            emp.full_name = full_name
        if department_id is not None:
            emp.department_id = department_id
        if is_approved is not None:
            emp.is_approved = is_approved
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
def create_qr_code():
    from apps.qr_generator.utils import generate_simple_qr_image_api
    qr = QRCode.objects.create(is_active=True)
    qr.generate_simple_image()
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
def assign_qr_to_device(qr_id, device_id):
    from apps.core.models import QRCode, Device
    try:
        qr = QRCode.objects.get(id=qr_id, is_active=True)
        device = Device.objects.get(id=device_id)
        if device.qr_code and device.qr_code != qr:
            old_qr = device.qr_code
            old_qr.device = None
            old_qr.save()
        qr.device = device
        qr.save()
        qr.generate_image()
        return True, f"QR {qr.code} привязан к устройству {device.inventory_number}"
    except Exception as e:
        return False, str(e)

@sync_to_async
def get_all_devices():
    from apps.core.models import Device
    return list(Device.objects.select_related('department', 'responsible').all().order_by('inventory_number'))

@sync_to_async
def get_devices_without_qr():
    from apps.core.models import Device
    return list(Device.objects.filter(qr_code__isnull=True).select_related('department', 'responsible').order_by('inventory_number'))

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
def create_device_with_qr(code, name, inventory_number, device_type_id, department_id=None, responsible_id=None):
    device = Device.objects.create(
        name=name,
        inventory_number=inventory_number,
        device_type_id=device_type_id,
        department_id=department_id,
        responsible_id=responsible_id,
        status=True
    )
    QRCode.objects.create(device=device, code=code, is_active=True)
    return device