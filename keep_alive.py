# keep_alive.py
from aiohttp import web
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Я жив!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# keep_alive.py


async def handle(request):
    return web.Response(text="Bot is alive!")

def keep_alive():
    app = web.Application()
    app.router.add_get("/", handle)
    web.run_app(app, host="0.0.0.0", port=8080)