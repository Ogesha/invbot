import asyncio

def run_async(coro):
    """
    Безопасно запускает асинхронную корутину из синхронного кода.
    Если цикл событий уже запущен, создаёт задачу в этом цикле,
    иначе использует asyncio.run().
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # Нет запущенного цикла – создаём новый
        return asyncio.run(coro)
    else:
        # Цикл уже запущен – создаём задачу
        # Возвращаем Future, но в синхронном коде мы не можем его ждать,
        # поэтому просто запускаем и не ждём результата.
        return loop.create_task(coro)