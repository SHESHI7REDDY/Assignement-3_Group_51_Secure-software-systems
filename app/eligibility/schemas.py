"""Strict request schemas (ELIG-03 input validation).

extra="forbid" rejects unexpected fields (mass-assignment); patterns and
length limits reject injection payloads before they reach the database.
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

VOTER_ID = r"^V\d{4,9}$"
NAME = r"^[A-Za-z][A-Za-z '\-]{1,79}$"
ADDRESS = r"^[A-Za-z0-9 ,.'/\-#]{5,120}$"
DIVISION = r"^[A-Za-z][A-Za-z \-]{1,39}$"
STATES = Literal["NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class VoterRef(Strict):
    voter_id: str = Field(pattern=VOTER_ID)


class AuthoriseRequest(Strict):
    voter_id: str = Field(pattern=VOTER_ID)
    channel: Literal["POLLING_STATION", "ONLINE", "OVERSEAS_MISSION"]


class RedeemRequest(Strict):
    ballot_token: str = Field(min_length=40, max_length=64, pattern=r"^[A-Za-z0-9_\-]+$")


class EnrolRequest(Strict):
    voter_id: str = Field(pattern=VOTER_ID)
    full_name: str = Field(pattern=NAME)
    date_of_birth: date
    citizenship: Literal["AU"]  # only citizens may enrol
    state: STATES
    division: str = Field(pattern=DIVISION)
    address: str = Field(pattern=ADDRESS)


class AddressUpdate(Strict):
    address: str = Field(pattern=ADDRESS)
    division: str = Field(pattern=DIVISION)


class MockTokenRequest(Strict):
    user_id: str = Field(pattern=r"^[A-Za-z0-9_\-]{2,32}$")
    role: Literal["voter", "officer", "service"]
    voter_id: str | None = Field(default=None, pattern=VOTER_ID)
