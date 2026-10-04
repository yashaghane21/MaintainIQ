"""Triage orchestration: evidence -> retrieval -> AI -> guardrails -> draft work order.

Failure policy:
* The issue is persisted before analysis and is never deleted on failure.
* A failed AI call is recorded in `analysis_history` with the error and the
  issue moves to `analysis_failed`; the client can retry.
* A retrieval failure does NOT block analysis; the model is told explicitly
  that no manual evidence is available.
"""

import time

from pymongo.database import Database

from app.core.config import get_settings
from app.core.errors import AIProviderError, ConflictError
from app.core.logging import get_logger
from app.models import Collections, IssueStatus, utcnow
from app.schemas.analysis import Evidence
from app.services import work_order_service
from app.services.ai_service import apply_guardrails, get_ai_provider
from app.services.equipment_service import get_equipment
from app.services.issue_service import get_issue, status_entry
from app.services.knowledge_service import ensure_index_loaded
from app.services.retrieval_service import RetrievalResult, RetrievalService

logger = get_logger(__name__)
EXCERPT_LIMIT = 700


def build_evidence(issue: dict, retrieval: RetrievalResult) -> list[Evidence]:
    """Every evidence item maps to real stored data or a real retrieved chunk."""
    evidence = [Evidence(
        evidence_id="E-USR-1", evidence_type="USER_REPORT", source=f"Issue report {issue['issue_id']}",
        title="Technician issue description", excerpt=issue["description"][:EXCERPT_LIMIT],
        metadata={"reported_by": issue.get("reported_by")},
    )]
    for i, event in enumerate(issue["operating_events"], start=1):
        evidence.append(Evidence(
            evidence_id=f"E-EVT-{i}", evidence_type="OPERATING_EVENT", source=f"Issue report {issue['issue_id']}",
            title=f"Operating event {i}", excerpt=event["description"],
            metadata={"occurred_at": event.get("occurred_at")},
        ))
    for i, finding in enumerate(issue["threshold_findings"], start=1):
        evidence.append(Evidence(
            evidence_id=f"E-RULE-{i}", evidence_type="SENSOR_RULE", source=f"Threshold rule {finding['rule_id']}",
            title=f"{finding['sensor']} - {finding['status']} ({finding['severity']})", excerpt=finding["explanation"],
            metadata={k: finding.get(k) for k in ("rule_id", "sensor", "status", "severity", "normalized_value",
                                                 "threshold_value", "unit", "is_stale")},
        ))
    for i, chunk in enumerate(retrieval.chunks, start=1):
        page = f", page {chunk.page_number}" if chunk.page_number else ""
        evidence.append(Evidence(
            evidence_id=f"E-DOC-{i}", evidence_type="MANUAL", source=f"{chunk.source}{page}",
            title=chunk.document_title, excerpt=chunk.text[:EXCERPT_LIMIT], document_id=chunk.document_id,
            chunk_id=chunk.chunk_id, page_number=chunk.page_number, retrieval_score=chunk.score,
        ))
    return evidence


def build_retrieval_query(issue: dict, equipment: dict) -> str:
    alarms = [f["explanation"] for f in issue["threshold_findings"] if f["severity"] in ("warning", "critical")]
    events = "; ".join(e["description"] for e in issue["operating_events"])
    return f"{equipment['name']} {issue['description']} {events} {' '.join(alarms)}"[:2000]


def build_context(issue: dict, equipment: dict, evidence: list[Evidence], retrieval: RetrievalResult, additional_context: str | None) -> dict:
    return {
        "equipment": {k: equipment.get(k) for k in ("equipment_id", "name", "equipment_type", "manufacturer", "model", "status")},
        "issue": {
            "description": issue["description"],
            "operating_events": issue["operating_events"],
            "sensor_readings": issue["sensor_readings"],
            "additional_context": additional_context,
        },
        "threshold_findings": issue["threshold_findings"],
        "highest_rule_severity": issue["threshold_summary"]["highest_severity"],
        "retrieval_status": retrieval.status,
        "retrieval_message": retrieval.message or f"{len(retrieval.chunks)} relevant manual excerpt(s) retrieved.",
        "evidence_catalogue": [e.model_dump(mode="json") for e in evidence],
    }


def analyze_issue(db: Database, issue_id: str, retrieval_service: RetrievalService, additional_context: str | None = None) -> dict:
    issue = get_issue(db, issue_id)
    if work_order_service.has_approved_work_order(db, issue_id):
        raise ConflictError("This issue already has an approved work order; re-analysis is not allowed.")
    equipment = get_equipment(db, issue["equipment_id"])
    version = len(issue.get("analysis_history") or []) + 1
    started = time.perf_counter()

    query = build_retrieval_query(issue, equipment)
    ensure_index_loaded(db, retrieval_service)
    retrieval = retrieval_service.retrieve(query, equipment_type=equipment["equipment_type"])
    logger.info("Retrieval finished", extra={"issue_id": issue_id, "retrieval_status": retrieval.status})

    evidence = build_evidence(issue, retrieval)
    context = build_context(issue, equipment, evidence, retrieval, additional_context)
    base_record = {
        "version": version,
        "started_at": utcnow(),
        "retrieval": {"status": retrieval.status, "message": retrieval.message, "query": query,
                      "chunks_used": len(retrieval.chunks)},
        "additional_context": additional_context,
    }

    provider_name = get_settings().ai_provider   # recorded even if the provider cannot be constructed
    try:
        provider = get_ai_provider()
        provider_name = provider.name
        run = provider.generate(context)
        guarded = apply_guardrails(run.output, {e.evidence_id for e in evidence}, context["highest_rule_severity"])
    except AIProviderError as exc:
        record = {**base_record, "status": "failed", "provider": provider_name, "error": {"code": exc.code, "message": exc.message,
                  "details": exc.details}, "completed_at": utcnow(), "duration_ms": int((time.perf_counter() - started) * 1000)}
        db[Collections.ISSUES].update_one({"issue_id": issue_id}, {
            "$set": {"status": IssueStatus.ANALYSIS_FAILED.value, "last_error": record["error"], "updated_at": utcnow()},
            "$push": {"analysis_history": record,
                      "status_history": status_entry(IssueStatus.ANALYSIS_FAILED.value, "system", exc.message)},
        })
        logger.warning("AI analysis failed; issue preserved", extra={"issue_id": issue_id, "ai_provider": provider_name, "ai_status": exc.code})
        raise

    record = {
        **base_record,
        "status": "completed",
        "provider": run.provider,
        "model": run.model,
        "is_simulated": run.is_simulated,
        "provider_attempts": run.raw_attempts,
        "output": guarded.data,
        "evidence": [e.model_dump(mode="json") for e in evidence],
        "validation_warnings": guarded.warnings,
        "completed_at": utcnow(),
        "duration_ms": int((time.perf_counter() - started) * 1000),
    }

    superseded = work_order_service.supersede_pending(db, issue_id, f"Superseded by analysis v{version}")
    db[Collections.ISSUES].update_one({"issue_id": issue_id}, {
        "$set": {"analysis": record, "priority": guarded.data["suggested_priority"], "last_error": None,
                 "status": IssueStatus.AWAITING_REVIEW.value, "updated_at": utcnow()},
        "$push": {"analysis_history": {k: v for k, v in record.items() if k != "evidence"} | {"evidence_count": len(evidence)},
                  "status_history": status_entry(IssueStatus.AWAITING_REVIEW.value, f"system: {run.provider}",
                                                 f"Analysis v{version} completed; draft work order awaiting review")},
    })
    work_order = work_order_service.create_from_analysis(db, issue, record)
    logger.info("AI analysis completed", extra={"issue_id": issue_id, "ai_provider": run.provider, "ai_status": "completed",
                                                 "work_order_id": work_order["work_order_id"]})
    result = get_issue(db, issue_id)
    result["superseded_work_orders"] = superseded
    return result


def get_evidence(db: Database, issue_id: str) -> dict:
    """Evidence of the latest successful analysis, with back-references to recommendations."""
    issue = get_issue(db, issue_id)
    analysis = issue.get("analysis")
    if not analysis:
        return {"issue_id": issue_id, "analysis_version": None, "evidence": [], "retrieval": None,
                "message": "No completed analysis yet."}
    usage: dict[str, list[dict]] = {}
    for kind, items, label in (("cause", analysis["output"]["possible_causes"], "cause"),
                               ("inspection_step", analysis["output"]["inspection_steps"], "step")):
        for idx, item in enumerate(items):
            for eid in item["evidence_ids"]:
                usage.setdefault(eid, []).append({"type": kind, "index": idx, "text": item[label]})
    evidence = [{**e, "referenced_by": usage.get(e["evidence_id"], [])} for e in analysis["evidence"]]
    return {"issue_id": issue_id, "analysis_version": analysis["version"], "evidence": evidence,
            "retrieval": analysis["retrieval"], "message": None}
