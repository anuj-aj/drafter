from pydantic import BaseModel, Field, field_validator
from typing import Any, Optional


class InteractionRequest(BaseModel):
    user_input: str = Field(..., min_length=1)

    @field_validator("user_input")
    @classmethod
    def no_blank_input(cls, v: str):
        if not v.strip():
            raise ValueError("Input cannot be blank")
        return v


class InteractionResponse(BaseModel):
    response: str

    # Optional draft payload returned when a proposal exists.
    # Kept flexible to avoid coupling clients to a rigid shape.
    draft: Optional[dict[str, Any]] = None
