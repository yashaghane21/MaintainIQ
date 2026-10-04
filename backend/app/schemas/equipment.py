from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

EquipmentType = Literal["pump", "hvac", "conveyor_motor"]
EquipmentStatusLiteral = Literal["operational", "degraded", "down", "maintenance"]


class EquipmentCreate(BaseModel):
    equipment_id: str = Field(min_length=3, max_length=40, pattern=r"^[A-Z0-9][A-Z0-9_-]*$",
                              description="Uppercase identifier, e.g. PUMP-004")
    name: str = Field(min_length=2, max_length=120)
    equipment_type: EquipmentType
    manufacturer: str = Field(min_length=1, max_length=120)
    model: str = Field(min_length=1, max_length=120)
    installation_date: date | None = None
    location: str | None = Field(default=None, max_length=120)
    status: EquipmentStatusLiteral = "operational"


class EquipmentOut(BaseModel):
    equipment_id: str
    name: str
    equipment_type: str
    manufacturer: str
    model: str
    installation_date: str | None = None
    location: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime
    open_issue_count: int = 0
    last_issue_at: datetime | None = None
