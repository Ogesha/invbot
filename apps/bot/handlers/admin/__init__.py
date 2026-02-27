from aiogram import Router
from . import departments, employees, qr_codes, requests, common, movements

def register_admin_handlers(router: Router):
    router.include_router(departments.router)
    router.include_router(employees.router)
    router.include_router(qr_codes.router)
    router.include_router(requests.router)
    router.include_router(movements.router)
    router.include_router(common.router)