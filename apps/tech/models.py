from apps.core.models import Computer, Printer

class ComputerProxy(Computer):
    class Meta:
        proxy = True
        app_label = 'tech'
        verbose_name = 'Компьютер'
        verbose_name_plural = 'Компьютеры'

class PrinterProxy(Printer):
    class Meta:
        proxy = True
        app_label = 'tech'
        verbose_name = 'Принтер'
        verbose_name_plural = 'Принтеры'