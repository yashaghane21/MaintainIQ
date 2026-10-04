"""Deterministic sensor threshold engine.

This module is intentionally free of any AI involvement: every finding is a
pure function of the readings, the configured profile and the reference time.

Rules of the engine:
* Missing readings are reported as `missing` and are never treated as zero.
* Non-finite, physically implausible or future-dated values are `invalid`.
* Units are converted to the profile's canonical unit; unknown units are
  reported as `unsupported_unit` and not evaluated.
* Readings older than the stale window are still evaluated but flagged.
* Several readings of one sensor that disagree produce an extra `conflict`
  finding; the most severe individual result is kept (safety-first).
"""

import json
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings
from app.schemas.threshold import SensorReadingIn, ThresholdEvaluation, ThresholdFinding

KNOWN_SENSORS = ("temperature", "pressure", "vibration", "operating_hours")
SEVERITY_RANK = {"unknown": -1, "normal": 0, "warning": 1, "critical": 2}
FUTURE_TOLERANCE = timedelta(minutes=5)

# unit alias -> (canonical unit, converter to canonical)
_UNIT_CONVERSIONS: dict[str, dict[str, tuple[str, callable]]] = {
    "temperature": {
        "c": ("C", lambda v: v), "°c": ("C", lambda v: v), "celsius": ("C", lambda v: v), "degc": ("C", lambda v: v),
        "f": ("C", lambda v: (v - 32) * 5 / 9), "°f": ("C", lambda v: (v - 32) * 5 / 9), "fahrenheit": ("C", lambda v: (v - 32) * 5 / 9),
        "k": ("C", lambda v: v - 273.15), "kelvin": ("C", lambda v: v - 273.15),
    },
    "pressure": {
        "bar": ("bar", lambda v: v), "psi": ("bar", lambda v: v * 0.0689476),
        "kpa": ("bar", lambda v: v / 100), "mpa": ("bar", lambda v: v * 10),
    },
    "vibration": {
        "mm/s": ("mm/s", lambda v: v), "in/s": ("mm/s", lambda v: v * 25.4), "ips": ("mm/s", lambda v: v * 25.4),
    },
    "operating_hours": {
        "h": ("h", lambda v: v), "hr": ("h", lambda v: v), "hrs": ("h", lambda v: v), "hours": ("h", lambda v: v),
    },
}


@lru_cache
def load_profiles(path: str | None = None) -> dict:
    path = path or get_settings().threshold_profiles_path
    with Path(path).open(encoding="utf-8") as fh:
        return json.load(fh)


def _normalize_sensor(name: str) -> str:
    return name.strip().lower().replace(" ", "_").replace("-", "_")


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _fmt(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".")


class ThresholdService:
    def __init__(self, profiles: dict | None = None, stale_minutes: int | None = None, conflict_tolerance: float | None = None):
        settings = get_settings()
        data = profiles if profiles is not None else load_profiles()
        self.disclaimer: str = data.get("disclaimer", "")
        self.profiles: dict = data["profiles"]
        self.stale_window = timedelta(minutes=stale_minutes if stale_minutes is not None else settings.stale_reading_minutes)
        self.conflict_tolerance = conflict_tolerance if conflict_tolerance is not None else settings.conflict_tolerance_ratio

    def evaluate(
        self,
        equipment_type: str,
        readings: list[SensorReadingIn],
        reference_time: datetime | None = None,
    ) -> ThresholdEvaluation:
        now = _as_utc(reference_time) or datetime.now(timezone.utc)
        profile = self.profiles.get(equipment_type)
        prefix = equipment_type.upper()
        findings: list[ThresholdFinding] = []
        evaluated_by_sensor: dict[str, list[ThresholdFinding]] = defaultdict(list)
        reported_sensors: set[str] = set()

        for reading in readings:
            sensor = _normalize_sensor(reading.sensor)
            reported_sensors.add(sensor)
            finding = self._evaluate_one(prefix, sensor, reading, profile, now)
            findings.append(finding)
            if finding.status == "evaluated":
                evaluated_by_sensor[sensor].append(finding)

        # Expected sensors with no reading at all -> explicit "missing" finding.
        if profile:
            for sensor, rule in profile["sensors"].items():
                if sensor not in reported_sensors:
                    findings.append(ThresholdFinding(
                        rule_id=f"{prefix}.{sensor.upper()}.MISSING", sensor=sensor, status="missing", severity="unknown",
                        unit=rule["canonical_unit"],
                        explanation=f"No {sensor.replace('_', ' ')} reading was provided. It was not evaluated and is not assumed to be zero.",
                    ))

        findings.extend(self._detect_conflicts(prefix, evaluated_by_sensor))

        evaluated = [f for f in findings if f.status in ("evaluated", "conflict")]
        highest = max((f.severity for f in evaluated), key=lambda s: SEVERITY_RANK[s], default="unknown")
        return ThresholdEvaluation(
            profile=equipment_type if profile else None,
            findings=findings,
            highest_severity=highest,
            evaluated_at=now,
            disclaimer=self.disclaimer,
        )

    # ------------------------------------------------------------------
    def _evaluate_one(self, prefix: str, sensor: str, reading: SensorReadingIn, profile: dict | None, now: datetime) -> ThresholdFinding:
        base = dict(sensor=sensor, observed_value=reading.value, observed_unit=reading.unit, recorded_at=_as_utc(reading.recorded_at))

        if sensor not in KNOWN_SENSORS or not profile or sensor not in profile["sensors"]:
            why = (f"Unknown sensor '{reading.sensor}'." if sensor not in KNOWN_SENSORS
                   else f"No threshold rule is configured for {sensor} on this equipment type.")
            return ThresholdFinding(rule_id=f"{prefix}.{sensor.upper()}.NO_RULE", status="no_rule", severity="unknown",
                                    explanation=f"{why} Reading recorded but not evaluated.", **base)

        rule = profile["sensors"][sensor]
        canonical = rule["canonical_unit"]
        rid = f"{prefix}.{sensor.upper()}"

        if reading.value is None:
            return ThresholdFinding(rule_id=f"{rid}.MISSING", status="missing", severity="unknown", unit=canonical,
                                    explanation="Reading was listed without a value. Not evaluated; not assumed to be zero.", **base)

        if not math.isfinite(reading.value):
            return ThresholdFinding(rule_id=f"{rid}.INVALID", status="invalid", severity="unknown", unit=canonical,
                                    explanation="Reading is not a finite number. Verify the sensor and data pipeline.", **base)

        recorded_at = base["recorded_at"]
        if recorded_at and recorded_at - now > FUTURE_TOLERANCE:
            return ThresholdFinding(rule_id=f"{rid}.INVALID", status="invalid", severity="unknown", unit=canonical,
                                    explanation="Reading timestamp is in the future. Check the sensor clock before trusting this value.", **base)

        unit_note = ""
        if reading.unit is None or not reading.unit.strip():
            converted, unit_note = reading.value, f" No unit supplied; assumed {canonical}."
        else:
            conv = _UNIT_CONVERSIONS[sensor].get(reading.unit.strip().lower())
            if conv is None:
                return ThresholdFinding(rule_id=f"{rid}.UNSUPPORTED_UNIT", status="unsupported_unit", severity="unknown", unit=canonical,
                                        explanation=f"Unit '{reading.unit}' cannot be converted to {canonical}. Not evaluated.", **base)
            converted = conv[1](reading.value)

        if converted < rule["plausible_min"] or converted > rule["plausible_max"]:
            return ThresholdFinding(rule_id=f"{rid}.INVALID", status="invalid", severity="unknown", normalized_value=round(converted, 3), unit=canonical,
                                    explanation=(f"{_fmt(converted)} {canonical} is outside the plausible range "
                                                 f"({_fmt(rule['plausible_min'])}–{_fmt(rule['plausible_max'])} {canonical}). Possible sensor fault."), **base)

        if converted > rule["critical"]:
            severity, threshold, rule_id = "critical", rule["critical"], f"{rid}.CRITICAL"
            text = f"{_fmt(converted)} {canonical} exceeds the critical threshold of {_fmt(threshold)} {canonical}."
        elif converted > rule["warning"]:
            severity, threshold, rule_id = "warning", rule["warning"], f"{rid}.WARNING"
            text = f"{_fmt(converted)} {canonical} exceeds the warning threshold of {_fmt(threshold)} {canonical}."
        else:
            severity, threshold, rule_id = "normal", rule["warning"], f"{rid}.RANGE"
            text = f"{_fmt(converted)} {canonical} is within the configured range (warning above {_fmt(threshold)} {canonical})."

        is_stale = bool(recorded_at and now - recorded_at > self.stale_window)
        if is_stale:
            age_min = int((now - recorded_at).total_seconds() // 60)
            text += f" STALE: reading is {age_min} minutes old and may not reflect current conditions."

        return ThresholdFinding(rule_id=rule_id, status="evaluated", severity=severity, normalized_value=round(converted, 3),
                                threshold_value=threshold, unit=canonical, explanation=text + unit_note, is_stale=is_stale, **base)

    def _detect_conflicts(self, prefix: str, evaluated: dict[str, list[ThresholdFinding]]) -> list[ThresholdFinding]:
        conflicts = []
        for sensor, items in evaluated.items():
            if len(items) < 2:
                continue
            values = [f.normalized_value for f in items]
            lo, hi = min(values), max(values)
            if hi - lo > self.conflict_tolerance * max(abs(hi), 1.0):
                worst = max(items, key=lambda f: SEVERITY_RANK[f.severity])
                conflicts.append(ThresholdFinding(
                    rule_id=f"{prefix}.{sensor.upper()}.CONFLICT", sensor=sensor, status="conflict", severity=worst.severity,
                    normalized_value=hi, threshold_value=worst.threshold_value, unit=items[0].unit,
                    explanation=(f"{len(items)} {sensor} readings disagree ({_fmt(lo)}–{_fmt(hi)} {items[0].unit}). "
                                 f"Treating the most severe result ({worst.severity}) as authoritative until the sensor is verified."),
                ))
        return conflicts
