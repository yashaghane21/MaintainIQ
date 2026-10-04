from typing import Literal

from fastapi import APIRouter, Depends, Query
from pymongo.database import Database

from app.core.database import get_database
from app.schemas.work_order import WorkOrderApprove, WorkOrderReject, WorkOrderUpdate
from app.services import work_order_service

router = APIRouter(prefix="/api/work-orders", tags=["work orders"])


@router.get("")
def list_work_orders(
    status_filter: Literal["pending_review", "approved", "rejected", "superseded"] | None = Query(default=None, alias="status"),
    priority: Literal["low", "medium", "high", "critical"] | None = None,
    equipment_id: str | None = None,
    issue_id: str | None = None,
    db: Database = Depends(get_database),
):
    return work_order_service.list_work_orders(db, status=status_filter, priority=priority,
                                               equipment_id=equipment_id, issue_id=issue_id)


@router.get("/{work_order_id}")
def get_work_order(work_order_id: str, db: Database = Depends(get_database)):
    return work_order_service.get_work_order(db, work_order_id)


@router.patch("/{work_order_id}")
def update_work_order(work_order_id: str, payload: WorkOrderUpdate, db: Database = Depends(get_database)):
    return work_order_service.update_work_order(db, work_order_id, payload)


@router.post("/{work_order_id}/approve")
def approve_work_order(work_order_id: str, payload: WorkOrderApprove, db: Database = Depends(get_database)):
    """Human decision endpoint. Requires reviewer identity and confirm=true."""
    return work_order_service.approve_work_order(db, work_order_id, payload)


@router.post("/{work_order_id}/reject")
def reject_work_order(work_order_id: str, payload: WorkOrderReject, db: Database = Depends(get_database)):
    """Human decision endpoint. Requires reviewer identity, a reason and confirm=true."""
    return work_order_service.reject_work_order(db, work_order_id, payload)
