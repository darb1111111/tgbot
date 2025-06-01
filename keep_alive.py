# keep_alive.py

from aiohttp import web

app = web.Application()

async def hello(request):
    return web.Response(text="Бот жив! 🙂")

app.add_routes([web.get("/", hello)])