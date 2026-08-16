from datetime import datetime
from pydantic import BaseModel, Field


class JobCreate(BaseModel):
    topic: str = Field(min_length=3, max_length=500)
    language: str = Field(default="th", max_length=10)
    target_seconds: int = Field(default=45, ge=15, le=90)


class JobRead(BaseModel):
    id: str
    topic: str
    language: str
    target_seconds: int
    status: str
    current_stage: str | None
    error: str | None
    artifacts: dict
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}

