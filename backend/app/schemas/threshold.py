from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

SensorName = Literal["temperature", "pressure", "vibration", "operating_hours"]

# How a reading was handled by the rule engine.
FindingStatus = Literal[
    "evaluated",        # value compared against thresholds
    "missing",          # expected sensor not reported (never treated as zero)
    "invalid",          # non-finite or physically implausible value
    "unsupported_unit", # unit we cannot convert -> not evaluated
    "no_rule",          # no threshold defined for this sensor on this equipment type
    "conflict",         # several readings for one sensor disagree
]
Severity = Literal["normal", "warning", "critical", "unknown"]


class SensorReadingIn(BaseModel):
    sensor: str = Field(min_length=1, max_length=50, description="temperature | pressure | vibration | operating_hours")
    value: float | None = Field(default=None, description="Numeric reading. Omit or null when not available.")
    unit: str | None = Field(default=None, max_length=20)
    recorded_at: datetime | None = None


class ThresholdFinding(BaseModel):
    rule_id: str
    sensor: str
    status: FindingStatus
    severity: Severity
    observed_value: float | None = None
    observed_unit: str | None = None
    normalized_value: float | None = None
    threshold_value: float | None = None
    unit: str | None = None
    explanation: str
    recorded_at: datetime | None = None
    is_stale: bool = False


class ThresholdEvaluation(BaseModel):
    profile: str | None
    findings: list[ThresholdFinding]
    highest_severity: Severity
    evaluated_at: datetime
    disclaimer: str
