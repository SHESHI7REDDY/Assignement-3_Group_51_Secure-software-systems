"""Only election and ranked candidate choices may be submitted by a voter."""
from pydantic import BaseModel, ConfigDict, Field


class Preference(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    candidate_id: str = Field(min_length=1, max_length=64)
    rank: int = Field(ge=1, le=1000)


class BallotSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    election_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    preferences: list[Preference] = Field(min_length=1, max_length=1000)
