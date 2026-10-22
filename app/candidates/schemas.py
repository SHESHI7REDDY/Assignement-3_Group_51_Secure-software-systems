
from pydantic import BaseModel, ConfigDict, Field


class CandidateCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        str_strip_whitespace=True,
    )

    election_id: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
    )

    name: str = Field(min_length=1, max_length=120)
    party: str = Field(min_length=1, max_length=120)
    ballot_order: int = Field(ge=1, le=1000)