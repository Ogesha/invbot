from django.contrib import admin
from .models import DepartmentProxy, EmployeeProxy, RegistrationRequestProxy
from apps.core.admin.base import DepartmentAdmin, EmployeeAdmin, RegistrationRequestAdmin

admin.site.register(DepartmentProxy, DepartmentAdmin)
admin.site.register(EmployeeProxy, EmployeeAdmin)
admin.site.register(RegistrationRequestProxy, RegistrationRequestAdmin)