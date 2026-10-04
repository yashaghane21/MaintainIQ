from fastapi import APIRouter, Depends, Query, status
from pymongo.database import Database

from app.core.database import get_database
from app.schemas.equipment import EquipmentCreate, EquipmentOut
from app.services import equipment_service

router = APIRouter(prefix="/api/equipment", tags=["equipment"])


@router.get("", response_model=list[EquipmentOut])
def list_equipment(
    search: str | None = Query(default=None, max_length=100),
    equipment_type: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    db: Database = Depends(get_database),
):
    return equipment_service.list_equipment(db, search, equipment_type, status_filter)


@router.post("", response_model=EquipmentOut, status_code=status.HTTP_201_CREATED)
def create_equipment(payload: EquipmentCreate, db: Database = Depends(get_database)):
    return equipment_service.create_equipment(db, payload)


@router.get("/{equipment_id}", response_model=EquipmentOut)
def get_equipment(equipment_id: str, db: Database = Depends(get_database)):
    return equipment_service.get_equipment_detail(db, equipment_id)


@router.get("/{equipment_id}/history")
def get_history(equipment_id: str, db: Database = Depends(get_database)):
    return equipment_service.get_history(db, equipment_id)
