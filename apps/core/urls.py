from django.urls import path
from . import views

urlpatterns = [
    path('admin/generate-qr-with-path/', views.generate_qr_with_path, name='generate_qr_with_path'),
    path('admin/assign-qr-to-device/', views.assign_qr_to_device, name='assign_qr_to_device'),
    path('admin/import-devices/', views.import_devices_from_excel, name='import_devices'),
    path('api/qr/', views.generate_qr_api, name='generate_qr_api'),
    path('api/device/<int:device_id>/qr/', views.device_qr_api, name='device_qr_api'),
    path('computer-list-partial/', views.computer_list_partial, name='computer_list_partial'),
    path('get-employees-by-department/', views.get_employees_by_department, name='get_employees_by_department'),
    path('api/movement-card/print/', views.movement_card_print_endpoint, name='movement_card_print_endpoint'),
]