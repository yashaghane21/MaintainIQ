from typing import Literal

from fastapi import APIRouter, Body, Depends, Query, status
from pymongo.database import Database

from app.core.database import get_database
from app.schemas.issue import AnalyzeRequest, IssueCreate
from app.services import issue_service, triage_service
from app.services.retrieval_service import get_retrieval_service

router = APIRouter(prefix="/api/issues", tags=["issues"])

IssueStatusFilter = Literal["reported", "analysis_failed", "awaiting_review", "work_order_approved", "work_order_rejected"]
PriorityFilter = Literal["low", "medium", "high", "critical"]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_issue(payload: IssueCreate, db: Database = Depends(get_database)):
    """Persist an issue and run deterministic threshold rules. AI analysis is a separate step."""
    return issue_service.create_issue(db, payload)


@router.get("")
def list_issues(
    equipment_id: str | None = None,
    priority: PriorityFilter | None = None,
    status_filter: IssueStatusFilter | None = Query(default=None, alias="status"),
    date_from: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}"),
    date_to: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}"),
    search: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=100, ge=1, le=500),
    db: Database = Depends(get_database),
):
    return issue_service.list_issues(db, equipment_id=equipment_id, priority=priority, status=status_filter,
                                     date_from=date_from, date_to=date_to, search=search, limit=limit)


@router.get("/{issue_id}")
def get_issue(issue_id: str, db: Database = Depends(get_database)):
    return issue_service.get_issue(db, issue_id)


@router.post("/{issue_id}/analyze")
def analyze_issue(issue_id: str, payload: AnalyzeRequest | None = Body(default=None), db: Database = Depends(get_database)):
    """Run retrieval + AI triage. On provider failure returns 502; the issue and failure are persisted."""
    return triage_service.analyze_issue(db, issue_id, get_retrieval_service(),
                                        additional_context=payload.additional_context if payload else None)


@router.get("/{issue_id}/evidence")
def get_evidence(issue_id: str, db: Database = Depends(get_database)):
    return triage_service.get_evidence(db, issue_id)
