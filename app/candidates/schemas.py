"""Validated models for candidate creation and editing."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


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

    name: str = Field(
        min_length=1,
        max_length=120,
    )

    party: str = Field(
        min_length=1,
        max_length=120,
    )

    ballot_order: int = Field(
        ge=1,
        le=1000,
    )


class CandidateUpdate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        str_strip_whitespace=True,
    )

    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=120,
    )

    party: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=120,
    )

    ballot_order: Optional[int] = Field(
        default=None,
        ge=1,
        le=1000,
    )

    @model_validator(mode="after")
    def validate_changes(self):
        if not self.model_fields_set:
            raise ValueError("Provide at least one editable field")

        if any(
            getattr(self, field) is None
            for field in self.model_fields_set
        ):
            raise ValueError("Editable fields cannot be null")

        return self