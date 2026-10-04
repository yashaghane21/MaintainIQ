"""AI provider abstraction and output guardrails.

Providers implement `generate(context) -> AIRunResult`. Whatever a provider
returns is validated against `AIAnalysisOutput` and then passed through
`apply_guardrails`, which:
  * drops evidence IDs that do not exist in the evidence catalogue (and logs it),
  * labels any cause/step left without evidence as an unverified hypothesis,
  * raises the priority to the deterministic rule-engine floor if needed.

There is deliberately no fallback from the live provider to the demo provider:
if Gemini fails the analysis attempt is recorded as failed and can be retried.
"""

import json
from dataclasses import dataclass, field

from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.errors import AIProviderError, AIResponseInvalidError
from app.core.logging import get_logger
from app.models import PRIORITY_RANK, Priority
from app.schemas.analysis import AIAnalysisOutput
from app.services.prompts import SYSTEM_INSTRUCTION, build_repair_prompt, build_user_prompt

logger = get_logger(__name__)


@dataclass
class AIRunResult:
    output: AIAnalysisOutput
    provider: str
    model: str
    is_simulated: bool
    raw_attempts: int = 1


class GeminiProvider:
    name = "gemini"
    is_simulated = False

    def __init__(self, settings: Settings, client=None):
        if not settings.gemini_api_key and client is None:
            raise AIProviderError("GEMINI_API_KEY is not configured on the server.")
        self.settings = settings
        self.model = settings.gemini_model
        self._client = client

    def _get_client(self):
        if self._client is None:
            from google import genai
            from google.genai import types

            self._client = genai.Client(
                api_key=self.settings.gemini_api_key,
                http_options=types.HttpOptions(timeout=self.settings.gemini_timeout_seconds * 1000),
            )
        return self._client

    def _call(self, prompt: str) -> str:
        from google.genai import types

        try:
            response = self._get_client().models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    temperature=self.settings.gemini_temperature,
                ),
            )
        except Exception as exc:  # noqa: BLE001 - SDK raises several error families
            code = getattr(exc, "code", None)
            raise AIProviderError(
                f"Gemini request failed ({type(exc).__name__}{f' {code}' if code else ''}).",
                details={"provider": "gemini", "error_type": type(exc).__name__, "status": code},
            ) from exc
        text = getattr(response, "text", None)
        if not text:
            raise AIResponseInvalidError("Gemini returned an empty response (possibly blocked by safety filters).")
        return text

    def generate(self, context: dict) -> AIRunResult:
        prompt = build_user_prompt(context)
        raw = self._call(prompt)
        try:
            return AIRunResult(parse_ai_output(raw), self.name, self.model, False, 1)
        except AIResponseInvalidError as first_error:
            # One repair attempt: give the model its validation error.
            logger.warning("Gemini output invalid; attempting repair", extra={"ai_status": "repairing"})
            raw2 = self._call(build_repair_prompt(prompt, raw, first_error.message))
            return AIRunResult(parse_ai_output(raw2), self.name, self.model, False, 2)


def parse_ai_output(raw: str | dict) -> AIAnalysisOutput:
    """Parse and strictly validate provider output."""
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError as exc:
        raise AIResponseInvalidError(f"AI response is not valid JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise AIResponseInvalidError("AI response must be a JSON object.")
    try:
        return AIAnalysisOutput.model_validate(data)
    except ValidationError as exc:
        errors = [{"field": ".".join(map(str, e["loc"])), "message": e["msg"]} for e in exc.errors()[:20]]
        raise AIResponseInvalidError("AI response failed schema validation.", details=errors) from exc


def rule_priority_floor(highest_severity: str) -> Priority:
    """Minimum priority implied by deterministic findings."""
    return {"critical": Priority.HIGH, "warning": Priority.MEDIUM}.get(highest_severity, Priority.LOW)


@dataclass
class GuardedAnalysis:
    data: dict
    warnings: list[str] = field(default_factory=list)


def apply_guardrails(output: AIAnalysisOutput, allowed_evidence_ids: set[str], highest_severity: str) -> GuardedAnalysis:
    data = output.model_dump()
    warnings: list[str] = []

    for section in ("possible_causes", "inspection_steps"):
        for item in data[section]:
            cited = item["evidence_ids"]
            valid = [e for e in dict.fromkeys(cited) if e in allowed_evidence_ids]
            invalid = [e for e in cited if e not in allowed_evidence_ids]
            if invalid:
                warnings.append(f"Removed unknown evidence reference(s) {invalid} from {section}.")
            item["evidence_ids"] = valid
            item["unverified"] = not valid   # no supporting evidence -> unverified hypothesis

    ai_priority = Priority(data["suggested_priority"])
    floor = rule_priority_floor(highest_severity)
    data["ai_suggested_priority"] = ai_priority.value
    if PRIORITY_RANK[ai_priority] < PRIORITY_RANK[floor]:
        data["suggested_priority"] = floor.value
        data["priority_adjustment"] = (
            f"Priority raised from {ai_priority.value} to {floor.value} because the rule engine reported a "
            f"{highest_severity} threshold finding."
        )
        warnings.append(data["priority_adjustment"])
    else:
        data["priority_adjustment"] = None
    return GuardedAnalysis(data, warnings)


def build_provider(settings: Settings | None = None):
    settings = settings or get_settings()
    if settings.ai_provider == "gemini":
        return GeminiProvider(settings)
    from app.services.demo_provider import DemoProvider

    return DemoProvider()


_provider_override = None


def get_ai_provider():
    """Returns the configured provider. Raises AIProviderError if misconfigured."""
    if _provider_override is not None:
        return _provider_override
    return build_provider()


def set_ai_provider(provider) -> None:
    """Test hook to inject a mock provider."""
    global _provider_override
    _provider_override = provider
