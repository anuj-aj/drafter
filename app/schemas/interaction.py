from pydantic import BaseModel, Field, field_validator


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
