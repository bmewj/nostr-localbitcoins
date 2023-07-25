from http import HTTPStatus

from fastapi import Depends, Request
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse

from lnbits.core.models import User
from lnbits.decorators import check_user_exists
from lnbits.settings import settings

from . import localbitcoins_ext, localbitcoins_renderer
from .crud import get_localbitcoins

templates = Jinja2Templates(directory="templates")


@localbitcoins_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return localbitcoins_renderer().TemplateResponse(
        "localbitcoins/index.html", {"request": request, "user": user.dict()}
    )


@localbitcoins_ext.get("/{localbitcoins_id}")
async def localbitcoins(request: Request, localbitcoins_id):
    localbitcoins = await get_localbitcoins(localbitcoins_id)
    if not localbitcoins:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="LocalBitcoins does not exist."
        )

    return localbitcoins_renderer().TemplateResponse(
        "localbitcoins/localbitcoins.html",
        {
            "request": request,
            "localbitcoins": localbitcoins,
            "web_manifest": f"/localbitcoins/manifest/{localbitcoins_id}.webmanifest",
        },
    )


@localbitcoins_ext.get("/manifest/{localbitcoins_id}.webmanifest")
async def manifest(localbitcoins_id: str):
    localbitcoins = await get_localbitcoins(localbitcoins_id)
    if not localbitcoins:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="LocalBitcoins does not exist."
        )

    return {
        "short_name": settings.lnbits_site_title,
        "name": localbitcoins.name + " - " + settings.lnbits_site_title,
        "icons": [
            {
                "src": settings.lnbits_custom_logo
                if settings.lnbits_custom_logo
                else "https://cdn.jsdelivr.net/gh/lnbits/lnbits@0.3.0/docs/logos/lnbits.png",
                "type": "image/png",
                "sizes": "900x900",
            }
        ],
        "start_url": "/localbitcoins/" + localbitcoins_id,
        "background_color": "#1F2234",
        "description": "P2P currency exchange marketplace built on Nostr",
        "display": "standalone",
        "scope": "/localbitcoins/" + localbitcoins_id,
        "theme_color": "#1F2234",
        "shortcuts": [
            {
                "name": localbitcoins.name + " - " + settings.lnbits_site_title,
                "short_name": localbitcoins.name,
                "description": localbitcoins.name + " - " + settings.lnbits_site_title,
                "url": "/localbitcoins/" + localbitcoins_id,
            }
        ],
    }
