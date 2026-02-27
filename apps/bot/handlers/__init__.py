from aiogram import Dispatcher


def register_all_handlers(dp: Dispatcher):
    from . import start, my_devices, list_devices, admin_create, common, qr_code
    from .admin import register_admin_handlers

    dp.include_router(start.router)
    dp.include_router(my_devices.router)
    dp.include_router(list_devices.router)
    dp.include_router(admin_create.router)
    register_admin_handlers(dp)
    dp.include_router(common.router)
    dp.include_router(qr_code.router)