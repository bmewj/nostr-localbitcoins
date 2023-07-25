from typing import List, Optional, Union

from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import CreateLocalBitcoinsData, LocalBitcoins


async def create_localbitcoins(wallet_id: str, data: CreateLocalBitcoinsData) -> LocalBitcoins:
    localbitcoins_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO localbitcoins.localbitcoinss (id, wallet, name, currency, tip_options, tip_wallet)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            localbitcoins_id,
            wallet_id,
            data.name,
            data.currency,
            data.tip_options,
            data.tip_wallet,
        ),
    )

    localbitcoins = await get_localbitcoins(localbitcoins_id)
    assert localbitcoins, "Newly created localbitcoins couldn't be retrieved"
    return localbitcoins


async def get_localbitcoins(localbitcoins_id: str) -> Optional[LocalBitcoins]:
    row = await db.fetchone("SELECT * FROM localbitcoins.localbitcoinss WHERE id = ?", (localbitcoins_id,))
    return LocalBitcoins(**row) if row else None


async def get_localbitcoinss(wallet_ids: Union[str, List[str]]) -> List[LocalBitcoins]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM localbitcoins.localbitcoinss WHERE wallet IN ({q})", (*wallet_ids,)
    )

    return [LocalBitcoins(**row) for row in rows]


async def delete_localbitcoins(localbitcoins_id: str) -> None:
    await db.execute("DELETE FROM localbitcoins.localbitcoinss WHERE id = ?", (localbitcoins_id,))
