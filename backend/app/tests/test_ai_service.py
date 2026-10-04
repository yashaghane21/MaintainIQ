import json
from types import SimpleNamespace

import pytest

from app.core.config import get_settings
from app.core.errors import AIProviderError, AIResponseInvalidError
from app.services.ai_service import GeminiProvider, apply_guardrails, parse_ai_output


def valid_output(**overrides):
    data = {
        "summary": "Pump shows high vibration consistent with bearing issues.",
        "observations": ["Vibration 9 mm/s reported"],
        "possible_causes": [{"cause": "Bearing wear", "reasoning": "Vibration plus heat.", "confidence": "medium",
                             "evidence_ids": ["E-RULE-1", "E-DOC-1"]}],
        "follow_up_questions": ["When did it start?"],
        "inspection_steps": [{"step": "Inspect bearings", "reason": "Test hypothesis", "evidence_ids": ["E-DOC-1"]}],
        "suggested_priority": "high",
        "priority_reason": "Critical vibration.",
        "work_order": {"title": "Inspect pump bearings", "description": "Inspect drive-end bearing housing.", "checklist": ["LOTO", "Inspect"]},
        "limitations": [],
    }
    data.update(overrides)
    return data


def test_valid_output_parses():
    out = parse_ai_output(json.dumps(valid_output()))
    assert out.suggested_priority == "high"


@pytest.mark.parametrize("bad", [
    {"suggested_priority": "urgent"},                                          # invalid enum
    {"possible_causes": [{"cause": "X cause", "reasoning": "because", "confidence": "certain", "evidence_ids": []}]},
    {"possible_causes": []},                                                   # at least one cause required
    {"work_order": {"title": "Fix", "description": "Short desc here", "checklist": []}},
    {"unexpected_field": "nope"},                                              # extra keys forbidden
])
def test_invalid_output_rejected(bad):
    with pytest.raises(AIResponseInvalidError):
        parse_ai_output(valid_output(**bad))


def test_missing_field_rejected():
    data = valid_output()
    del data["summary"]
    with pytest.raises(AIResponseInvalidError):
        parse_ai_output(data)


def test_non_json_rejected():
    with pytest.raises(AIResponseInvalidError):
        parse_ai_output("Sure! Here is my analysis: ...")


def test_guardrails_strip_fabricated_evidence_and_flag_unverified():
    out = parse_ai_output(valid_output(possible_causes=[
        {"cause": "Bearing wear", "reasoning": "Heat and noise.", "confidence": "low", "evidence_ids": ["E-DOC-1", "E-DOC-99"]},
        {"cause": "Cavitation", "reasoning": "Crackling sound.", "confidence": "low", "evidence_ids": ["E-FAKE-1"]},
    ]))
    guarded = apply_guardrails(out, {"E-DOC-1", "E-RULE-1"}, "normal")
    causes = guarded.data["possible_causes"]
    assert causes[0]["evidence_ids"] == ["E-DOC-1"] and causes[0]["unverified"] is False
    assert causes[1]["evidence_ids"] == [] and causes[1]["unverified"] is True
    assert any("E-DOC-99" in w for w in guarded.warnings)


def test_guardrails_raise_priority_to_rule_floor():
    out = parse_ai_output(valid_output(suggested_priority="low"))
    guarded = apply_guardrails(out, {"E-RULE-1", "E-DOC-1"}, "critical")
    assert guarded.data["suggested_priority"] == "high"
    assert guarded.data["ai_suggested_priority"] == "low"
    assert guarded.data["priority_adjustment"]


def test_guardrails_keep_higher_ai_priority():
    out = parse_ai_output(valid_output(suggested_priority="critical"))
    assert apply_guardrails(out, set(), "warning").data["suggested_priority"] == "critical"


# ---- Gemini provider with a mocked SDK client ---------------------------------
class FakeModels:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def generate_content(self, **kwargs):
        self.calls += 1
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return SimpleNamespace(text=item)


def gemini(responses):
    fake = SimpleNamespace(models=FakeModels(responses))
    settings = get_settings().model_copy(update={"ai_provider": "gemini"})
    return GeminiProvider(settings, client=fake), fake.models


CONTEXT = {"equipment": {}, "issue": {}, "threshold_findings": [], "evidence_catalogue": []}


def test_gemini_success():
    provider, models = gemini([json.dumps(valid_output())])
    result = provider.generate(CONTEXT)
    assert result.provider == "gemini" and result.is_simulated is False and models.calls == 1


def test_gemini_repairs_invalid_output_once():
    provider, models = gemini(["not json", json.dumps(valid_output())])
    result = provider.generate(CONTEXT)
    assert result.raw_attempts == 2 and models.calls == 2


def test_gemini_invalid_twice_raises():
    provider, _ = gemini(["not json", json.dumps({"summary": "x"})])
    with pytest.raises(AIResponseInvalidError):
        provider.generate(CONTEXT)


def test_gemini_network_error_raises_provider_error():
    provider, _ = gemini([ConnectionError("boom")])
    with pytest.raises(AIProviderError) as exc:
        provider.generate(CONTEXT)
    assert "ConnectionError" in exc.value.message


def test_gemini_requires_api_key():
    settings = get_settings().model_copy(update={"ai_provider": "gemini", "gemini_api_key": None})
    with pytest.raises(AIProviderError):
        GeminiProvider(settings)
