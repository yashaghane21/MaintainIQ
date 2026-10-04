from typing import Literal

from pydantic import BaseModel, Field, field_validator

PriorityLiteral = Literal["low", "medium", "high", "critical"]


class ChecklistItem(BaseModel):
    text: str = Field(min_length=1, max_length=400)
    done: bool = False


class WorkOrderUpdate(BaseModel):
    """Technician edits. Only allowed while the work order is pending review."""
    title: str | None = Field(default=None, min_length=5, max_length=160)
    description: str | None = Field(default=None, min_length=10, max_length=4000)
    priority: PriorityLiteral | None = None
    checklist: list[ChecklistItem] | None = Field(default=None, max_length=40)
    technician_notes: str | None = Field(default=None, max_length=4000)
    editor: str = Field(default="Demo Technician", min_length=2, max_length=80)

    @field_validator("checklist")
    @classmethod
    def _non_empty(cls, v):
        if v is not None and len(v) == 0:
            raise ValueError("Checklist must contain at least one item")
        return v


class WorkOrderDecisionBase(BaseModel):
    reviewer: str = Field(min_length=2, max_length=80)
    # Explicit human confirmation is required; the UI sets this only after the
    # technician confirms in a dialog.
    confirm: bool

    @field_validator("confirm")
    @classmethod
    def _must_confirm(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("Explicit confirmation (confirm=true) is required")
        return v


class WorkOrderApprove(WorkOrderDecisionBase):
    technician_notes: str | None = Field(default=None, max_length=4000)


class WorkOrderReject(WorkOrderDecisionBase):
    reason: str = Field(min_length=5, max_length=2000)
