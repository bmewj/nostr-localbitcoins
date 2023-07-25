import asyncio

from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import catch_everything_and_restart

db = Database("ext_localbitcoins")

localbitcoins_ext: APIRouter = APIRouter(prefix="/localbitcoins", tags=["LocalBitcoins"])
scheduled_tasks: list[asyncio.Task] = []

localbitcoins_static_files = [
    {
        "path": "/localbitcoins/static",
        "app": StaticFiles(directory="lnbits/extensions/localbitcoins/static"),
        "name": "localbitcoins_static",
    }
]


def localbitcoins_renderer():
    return template_renderer(["lnbits/extensions/localbitcoins/templates"])


from .tasks import wait_for_paid_invoices
from .views import *  # noqa
from .views_api import *  # noqa


def localbitcoins_start():
    loop = asyncio.get_event_loop()
    task = loop.create_task(catch_everything_and_restart(wait_for_paid_invoices))
    scheduled_tasks.append(task)
