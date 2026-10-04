"""Prompt construction for the triage model."""

import json

from app.schemas.analysis import AIAnalysisOutput

SYSTEM_INSTRUCTION = """You are MaintainIQ, a maintenance triage assistant that supports qualified technicians.
You produce a structured triage draft. A human technician reviews, edits, approves or rejects it.

Hard rules:
1. Possible causes are HYPOTHESES. Never state or imply a confirmed diagnosis.
2. Use only the sensor readings and rule findings provided. Never invent or estimate readings.
3. Never invent manual content. Only cite evidence IDs that appear in EVIDENCE_CATALOGUE.
   If a hypothesis or step has no supporting evidence, return an empty evidence_ids list; do not guess IDs.
4. Deterministic rule findings are authoritative facts about thresholds. Do not recompute or contradict them.
5. Never instruct anyone to bypass, disable or override safety systems, interlocks or guards.
6. You cannot approve work orders or control equipment. Do not claim to have done so.
7. Include lockout/tagout or equivalent isolation before any hands-on inspection step.
8. State uncertainty and missing information in `limitations` and ask targeted follow_up_questions.
9. Recommend review by a qualified technician when risk is high or information is insufficient.
10. Retrieval relevance scores are text-similarity values, not probabilities. Do not convert them into confidence.

Respond with a single JSON object matching OUTPUT_SCHEMA exactly. No markdown, no extra keys."""


def build_user_prompt(context: dict) -> str:
    schema = AIAnalysisOutput.model_json_schema()
    return (
        "TRIAGE_CONTEXT:\n"
        + json.dumps(context, indent=2, default=str)
        + "\n\nOUTPUT_SCHEMA (JSON Schema):\n"
        + json.dumps(schema)
        + "\n\nConstraints: confidence must be one of low|medium|high; suggested_priority one of "
          "low|medium|high|critical. `observations` must restate only facts present in the context."
    )


def build_repair_prompt(original_prompt: str, bad_output: str, error: str) -> str:
    return (
        original_prompt
        + "\n\nYour previous response failed validation with this error:\n"
        + error[:2000]
        + "\n\nPrevious response:\n"
        + bad_output[:6000]
        + "\n\nReturn a corrected JSON object that satisfies OUTPUT_SCHEMA."
    )
