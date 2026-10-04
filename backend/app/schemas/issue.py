from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.threshold import SensorReadingIn


class OperatingEventIn(BaseModel):
    description: str = Field(min_length=3, max_length=500)
    occurred_at: datetime | None = None


class IssueCreate(BaseModel):
    equipment_id: str = Field(min_length=1, max_length=40)
    description: str = Field(min_length=10, max_length=4000, description="What the technician observed")
    operating_events: list[OperatingEventIn] = Field(min_length=1, max_length=30)
    sensor_readings: list[SensorReadingIn] = Field(default_factory=list, max_length=40)
    reported_by: str | None = Field(default=None, max_length=80)

    @field_validator("description")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Description cannot be blank")
        return v.strip()


class AnalyzeRequest(BaseModel):
    # Optional extra context a technician can add before (re-)running analysis.
    additional_context: str | None = Field(default=None, max_length=2000)
