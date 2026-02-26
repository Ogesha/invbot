from apps.core.models import Department, Employee, RegistrationRequest

class DepartmentProxy(Department):
    class Meta:
        proxy = True
        app_label = 'staff'
        verbose_name = 'Отдел'
        verbose_name_plural = 'Отделы'

class EmployeeProxy(Employee):
    class Meta:
        proxy = True
        app_label = 'staff'
        verbose_name = 'Сотрудник'
        verbose_name_plural = 'Сотрудники'

class RegistrationRequestProxy(RegistrationRequest):
    class Meta:
        proxy = True
        app_label = 'staff'
        verbose_name = 'Заявка на регистрацию'
        verbose_name_plural = 'Заявки на регистрацию'