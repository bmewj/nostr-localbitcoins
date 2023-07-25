from http import HTTPStatus

import httpx
from fastapi import Depends, Query
from lnurl import decode as decode_lnurl
from loguru import logger
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_latest_payments_by_extension, get_user
from lnbits.core.models import Payment
from lnbits.core.services import create_invoice
from lnbits.core.views.api import api_payment
from lnbits.decorators import (
    WalletTypeInfo,
    check_admin,
    get_key_type,
    require_admin_key,
)
from lnbits.settings import settings
from lnbits.utils.exchange_rates import get_fiat_rate_satoshis

from . import scheduled_tasks, localbitcoins_ext
from .crud import create_localbitcoins, delete_localbitcoins, get_localbitcoins, get_localbitcoinss
from .models import CreateLocalBitcoinsData, PayLnurlWData


@localbitcoins_ext.get("/api/v1/localbitcoinss", status_code=HTTPStatus.OK)
async def api_localbitcoinss(
    all_wallets: bool = Query(False), wallet: WalletTypeInfo = Depends(get_key_type)
):
    wallet_ids = [wallet.wallet.id]
    if all_wallets:
        user = await get_user(wallet.wallet.user)
        wallet_ids = user.wallet_ids if user else []

    return [localbitcoins.dict() for localbitcoins in await get_localbitcoinss(wallet_ids)]


@localbitcoins_ext.post("/api/v1/localbitcoinss", status_code=HTTPStatus.CREATED)
async def api_localbitcoins_create(
    data: CreateLocalBitcoinsData, wallet: WalletTypeInfo = Depends(get_key_type)
):
    localbitcoins = await create_localbitcoins(wallet_id=wallet.wallet.id, data=data)
    return localbitcoins.dict()


@localbitcoins_ext.delete("/api/v1/localbitcoinss/{localbitcoins_id}")
async def api_localbitcoins_delete(
    localbitcoins_id: str, wallet: WalletTypeInfo = Depends(require_admin_key)
):
    localbitcoins = await get_localbitcoins(localbitcoins_id)

    if not localbitcoins:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="LocalBitcoins does not exist."
        )

    if localbitcoins.wallet != wallet.wallet.id:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Not your LocalBitcoins.")

    await delete_localbitcoins(localbitcoins_id)
    return "", HTTPStatus.NO_CONTENT


@localbitcoins_ext.post("/api/v1/localbitcoinss/{localbitcoins_id}/invoices", status_code=HTTPStatus.CREATED)
async def api_localbitcoins_create_invoice(
    localbitcoins_id: str, amount: int = Query(..., ge=1), memo: str = "", tipAmount: int = 0
) -> dict:

    localbitcoins = await get_localbitcoins(localbitcoins_id)

    if not localbitcoins:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="LocalBitcoins does not exist."
        )

    if tipAmount > 0:
        amount += tipAmount

    try:
        payment_hash, payment_request = await create_invoice(
            wallet_id=localbitcoins.wallet,
            amount=amount,
            memo=f"{memo} to {localbitcoins.name}" if memo else f"{localbitcoins.name}",
            extra={
                "tag": "localbitcoins",
                "tipAmount": tipAmount,
                "localbitcoinsId": localbitcoins_id,
                "amount": amount - tipAmount if tipAmount else False,
            },
        )
    except Exception as e:
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e))

    return {"payment_hash": payment_hash, "payment_request": payment_request}


@localbitcoins_ext.get("/api/v1/localbitcoinss/{localbitcoins_id}/invoices")
async def api_localbitcoins_get_latest_invoices(localbitcoins_id: str):
    try:
        payments = [
            Payment.from_row(row)
            for row in await get_latest_payments_by_extension(
                ext_name="localbitcoins", ext_id=localbitcoins_id
            )
        ]

    except Exception as e:
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e))

    return [
        {
            "checking_id": payment.checking_id,
            "amount": payment.amount,
            "time": payment.time,
            "pending": payment.pending,
        }
        for payment in payments
    ]


@localbitcoins_ext.post(
    "/api/v1/localbitcoinss/{localbitcoins_id}/invoices/{payment_request}/pay", status_code=HTTPStatus.OK
)
async def api_localbitcoins_pay_invoice(
    lnurl_data: PayLnurlWData, payment_request: str, localbitcoins_id: str
):
    localbitcoins = await get_localbitcoins(localbitcoins_id)

    if not localbitcoins:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="LocalBitcoins does not exist."
        )

    lnurl = (
        lnurl_data.lnurl.replace("lnurlw://", "")
        .replace("lightning://", "")
        .replace("LIGHTNING://", "")
        .replace("lightning:", "")
        .replace("LIGHTNING:", "")
    )

    if lnurl.lower().startswith("lnurl"):
        lnurl = decode_lnurl(lnurl)
    else:
        lnurl = "https://" + lnurl

    async with httpx.AsyncClient() as client:
        try:
            headers = {"user-agent": f"lnbits/localbitcoins commit {settings.lnbits_commit[:7]}"}
            r = await client.get(lnurl, follow_redirects=True, headers=headers)
            if r.is_error:
                lnurl_response = {"success": False, "detail": "Error loading"}
            else:
                resp = r.json()
                if resp["tag"] != "withdrawRequest":
                    lnurl_response = {"success": False, "detail": "Wrong tag type"}
                else:
                    r2 = await client.get(
                        resp["callback"],
                        follow_redirects=True,
                        headers=headers,
                        params={
                            "k1": resp["k1"],
                            "pr": payment_request,
                        },
                    )
                    resp2 = r2.json()
                    if r2.is_error:
                        lnurl_response = {
                            "success": False,
                            "detail": "Error loading callback",
                        }
                    elif resp2["status"] == "ERROR":
                        lnurl_response = {"success": False, "detail": resp2["reason"]}
                    else:
                        lnurl_response = {"success": True, "detail": resp2}
        except (httpx.ConnectError, httpx.RequestError):
            lnurl_response = {"success": False, "detail": "Unexpected error occurred"}

    return lnurl_response


@localbitcoins_ext.get(
    "/api/v1/localbitcoinss/{localbitcoins_id}/invoices/{payment_hash}", status_code=HTTPStatus.OK
)
async def api_localbitcoins_check_invoice(localbitcoins_id: str, payment_hash: str):
    localbitcoins = await get_localbitcoins(localbitcoins_id)
    if not localbitcoins:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="LocalBitcoins does not exist."
        )
    try:
        status = await api_payment(payment_hash)

    except Exception as exc:
        logger.error(exc)
        return {"paid": False}
    return status


@localbitcoins_ext.delete(
    "/api/v1",
    status_code=HTTPStatus.OK,
    dependencies=[Depends(check_admin)],
    description="Stop the extension.",
)
async def api_stop():
    for t in scheduled_tasks:
        try:
            t.cancel()
        except Exception as ex:
            logger.warning(ex)

    return {"success": True}

@localbitcoins_ext.get("/api/v1/rate/{currency}", status_code=HTTPStatus.OK)
async def api_check_fiat_rate(currency):
    try:
        rate = await get_fiat_rate_satoshis(currency)
    except AssertionError:
        rate = None

    return {"rate": rate}