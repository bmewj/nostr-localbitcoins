from sqlite3 import Row
from typing import Optional

from fastapi import Query
from pydantic import BaseModel


class CreateLocalBitcoinsData(BaseModel):
    name: str
    wallet: str


class LocalBitcoins(BaseModel):
    id: str
    wallet: str
    name: str

    @classmethod
    def from_row(cls, row: Row) -> "LocalBitcoins":
        return cls(**dict(row))


class PayLnurlWData(BaseModel):
    lnurl: str
