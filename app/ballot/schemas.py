from typing import List

from pydantic import BaseModel, Field


class Preference(BaseModel):
    candidate_id: str = Field(..., min_length=1)
    rank: int = Field(..., ge=1)


class BallotSubmission(BaseModel):
    election_id: str = Field(..., min_length=1)
    preferences: List[Preference]
