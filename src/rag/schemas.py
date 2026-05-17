from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class WorkCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=256)


class WorkUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=256)


class WorkOut(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentOut(BaseModel):
    id: int
    work_id: int
    filename: str
    content_type: str
    size_bytes: int
    status: Literal["pending", "done", "failed"]
    chunk_count: int
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
