from django.contrib import admin
from .models import ComputerProxy, PrinterProxy
from apps.core.admin.device import ComputerAdmin, PrinterAdmin

admin.site.register(ComputerProxy, ComputerAdmin)
admin.site.register(PrinterProxy, PrinterAdmin)