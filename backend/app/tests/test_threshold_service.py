from datetime import datetime, timedelta, timezone

import pytest

from app.schemas.threshold import SensorReadingIn
from app.services.threshold_service import ThresholdService

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def svc():
    return ThresholdService(stale_minutes=120, conflict_tolerance=0.10)


def r(sensor, value, unit=None, minutes_ago=5):
    return SensorReadingIn(sensor=sensor, value=value, unit=unit,
                           recorded_at=NOW - timedelta(minutes=minutes_ago) if minutes_ago is not None else None)


def by_sensor(result, sensor, status=None):
    return [f for f in result.findings if f.sensor == sensor and (status is None or f.status == status)]


def test_normal_values(svc):
    res = svc.evaluate("pump", [r("temperature", 60, "C"), r("pressure", 6, "bar"), r("vibration", 3, "mm/s"),
                                r("operating_hours", 1000, "h")], NOW)
    assert res.highest_severity == "normal"
    assert all(f.status == "evaluated" and f.severity == "normal" for f in res.findings)
    assert by_sensor(res, "temperature")[0].rule_id == "PUMP.TEMPERATURE.RANGE"


def test_warning_threshold(svc):
    res = svc.evaluate("pump", [r("temperature", 80, "C")], NOW)
    f = by_sensor(res, "temperature", "evaluated")[0]
    assert (f.severity, f.threshold_value, f.unit, f.rule_id) == ("warning", 75, "C", "PUMP.TEMPERATURE.WARNING")
    assert f.observed_value == 80 and f.recorded_at is not None
    assert res.highest_severity == "warning"


def test_critical_threshold(svc):
    res = svc.evaluate("pump", [r("vibration", 8.5, "mm/s"), r("pressure", 10.5, "bar")], NOW)
    assert {f.severity for f in res.findings if f.status == "evaluated"} == {"critical"}
    assert res.highest_severity == "critical"


def test_boundary_is_not_exceeded(svc):
    # Thresholds are "above": exactly 75 C is not a warning.
    f = by_sensor(svc.evaluate("pump", [r("temperature", 75, "C")], NOW), "temperature", "evaluated")[0]
    assert f.severity == "normal"


def test_missing_readings_are_never_zero(svc):
    res = svc.evaluate("pump", [r("temperature", 60, "C"), r("pressure", None, "bar")], NOW)
    pressure = by_sensor(res, "pressure")[0]
    assert pressure.status == "missing" and pressure.severity == "unknown"
    assert pressure.normalized_value is None and pressure.observed_value is None
    # vibration + operating hours not supplied at all -> also reported missing
    assert by_sensor(res, "vibration")[0].status == "missing"
    assert by_sensor(res, "operating_hours")[0].status == "missing"


def test_all_missing_gives_unknown_overall(svc):
    res = svc.evaluate("pump", [], NOW)
    assert res.highest_severity == "unknown"
    assert all(f.status == "missing" for f in res.findings)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -500.0, 9999.0])
def test_invalid_values(svc, value):
    f = by_sensor(svc.evaluate("pump", [r("temperature", value, "C")], NOW), "temperature")[0]
    assert f.status == "invalid" and f.severity == "unknown"


def test_negative_vibration_is_invalid(svc):
    assert by_sensor(svc.evaluate("pump", [r("vibration", -1, "mm/s")], NOW), "vibration")[0].status == "invalid"


def test_future_timestamp_is_invalid(svc):
    f = by_sensor(svc.evaluate("pump", [r("temperature", 60, "C", minutes_ago=-60)], NOW), "temperature")[0]
    assert f.status == "invalid"


def test_unit_conversion(svc):
    # 194 F = 90 C (not above critical 90) -> warning; 150 psi ≈ 10.34 bar -> critical
    res = svc.evaluate("pump", [r("temperature", 194, "F"), r("pressure", 150, "psi")], NOW)
    temp = by_sensor(res, "temperature", "evaluated")[0]
    assert temp.normalized_value == pytest.approx(90.0) and temp.severity == "warning"
    assert by_sensor(res, "pressure", "evaluated")[0].severity == "critical"


def test_unsupported_unit_not_evaluated(svc):
    f = by_sensor(svc.evaluate("pump", [r("pressure", 5, "atmospheres")], NOW), "pressure")[0]
    assert f.status == "unsupported_unit" and f.severity == "unknown"


def test_missing_unit_assumes_canonical_and_says_so(svc):
    f = by_sensor(svc.evaluate("pump", [r("vibration", 6)], NOW), "vibration")[0]
    assert f.severity == "warning" and "assumed mm/s" in f.explanation


def test_stale_reading_flagged(svc):
    f = by_sensor(svc.evaluate("pump", [r("temperature", 92, "C", minutes_ago=300)], NOW), "temperature")[0]
    assert f.is_stale and f.severity == "critical" and "STALE" in f.explanation


def test_conflicting_readings(svc):
    res = svc.evaluate("pump", [r("temperature", 60, "C"), r("temperature", 95, "C")], NOW)
    conflict = by_sensor(res, "temperature", "conflict")
    assert len(conflict) == 1
    assert conflict[0].severity == "critical"   # safety-first: most severe wins
    assert res.highest_severity == "critical"


def test_close_readings_do_not_conflict(svc):
    res = svc.evaluate("pump", [r("temperature", 60, "C"), r("temperature", 62, "C")], NOW)
    assert not by_sensor(res, "temperature", "conflict")


def test_sensor_without_rule_for_type(svc):
    f = by_sensor(svc.evaluate("conveyor_motor", [r("pressure", 3, "bar")], NOW), "pressure")[0]
    assert f.status == "no_rule"


def test_unknown_sensor_and_unknown_profile(svc):
    assert by_sensor(svc.evaluate("pump", [r("humidity", 50, "%")], NOW), "humidity")[0].status == "no_rule"
    res = svc.evaluate("turbine", [r("temperature", 50, "C")], NOW)
    assert res.profile is None and res.findings[0].status == "no_rule"
