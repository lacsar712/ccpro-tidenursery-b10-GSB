from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.feed_allocation import FeedAllocation
from app.models.feed_event import FeedEvent
from app.models.meter_reading import MeterReading
from app.models.pond import Pond
from app.models.user import User
from app.schemas.meter_reading import (
    AllocationCreate,
    AllocationOut,
    MeterReadingCreate,
    MeterReadingOut,
    ReconciliationOut,
)

router = APIRouter(prefix="/api/meter-readings", tags=["meter-readings"])

# 封抄时电量 / 电费允许误差
TOLERANCE = 0.01


def _get_reading_or_404(db: Session, reading_id: int) -> MeterReading:
    reading = (
        db.query(MeterReading).filter(MeterReading.id == reading_id).first()
    )
    if not reading:
        raise HTTPException(status_code=404, detail="抄见不存在")
    return reading


@router.get("", response_model=List[MeterReadingOut])
def list_readings(
    pond_id: Optional[int] = Query(None, alias="pondId"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(MeterReading)
    if pond_id is not None:
        q = q.filter(MeterReading.pond_id == pond_id)
    return q.order_by(
        MeterReading.reading_date.desc(), MeterReading.id.desc()
    ).all()


@router.post("", response_model=MeterReadingOut, status_code=status.HTTP_201_CREATED)
def create_reading(
    payload: MeterReadingCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    pond = db.query(Pond).filter(Pond.id == payload.pond_id).first()
    if not pond:
        raise HTTPException(status_code=400, detail="塘口不存在")
    item = MeterReading(
        pond_id=payload.pond_id,
        reading_date=payload.reading_date,
        start_kwh=payload.start_kwh,
        end_kwh=payload.end_kwh,
        unit_price=payload.unit_price,
    )
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="该塘口同日已有抄见")
    db.refresh(item)
    return item


@router.get("/{reading_id}", response_model=MeterReadingOut)
def get_reading(
    reading_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return _get_reading_or_404(db, reading_id)


@router.delete("/{reading_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reading(
    reading_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    item = _get_reading_or_404(db, reading_id)
    if item.sealed:
        raise HTTPException(status_code=409, detail="已封抄见不能删除")
    db.delete(item)
    db.commit()


@router.post(
    "/{reading_id}/allocations",
    response_model=AllocationOut,
    status_code=status.HTTP_201_CREATED,
)
def add_allocation(
    reading_id: int,
    payload: AllocationCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    reading = _get_reading_or_404(db, reading_id)
    if reading.sealed:
        raise HTTPException(status_code=409, detail="抄见已封账，不能再挂投喂")

    feed = db.query(FeedEvent).filter(FeedEvent.id == payload.feed_event_id).first()
    if not feed:
        raise HTTPException(status_code=400, detail="投喂记录不存在")
    if feed.pond_id != reading.pond_id:
        raise HTTPException(status_code=400, detail="投喂必须属于同一塘口")

    existing = (
        db.query(FeedAllocation)
        .filter(FeedAllocation.feed_event_id == payload.feed_event_id)
        .first()
    )
    if existing:
        if existing.meter_reading_id == reading_id:
            return existing  # 重复挂同一笔，幂等返回
        raise HTTPException(status_code=409, detail="该投喂已挂在另一张抄见上")

    item = FeedAllocation(
        meter_reading_id=reading_id, feed_event_id=payload.feed_event_id
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete(
    "/{reading_id}/allocations/{allocation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_allocation(
    reading_id: int,
    allocation_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    reading = _get_reading_or_404(db, reading_id)
    if reading.sealed:
        raise HTTPException(status_code=409, detail="抄见已封账，不能取消挂账")
    item = (
        db.query(FeedAllocation)
        .filter(
            FeedAllocation.id == allocation_id,
            FeedAllocation.meter_reading_id == reading_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="分摊明细不存在")
    db.delete(item)
    db.commit()


@router.post("/{reading_id}/seal", response_model=MeterReadingOut)
def seal_reading(
    reading_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    reading = _get_reading_or_404(db, reading_id)
    if reading.sealed:
        raise HTTPException(status_code=409, detail="抄见已封账")
    if len(reading.allocations) < 2:
        raise HTTPException(status_code=409, detail="至少挂两笔投喂才能封抄")

    # 电量 = 止度 - 起度；电费 = 电量 × 单价（误差不超过 0.01）
    kwh = reading.end_kwh - reading.start_kwh
    fee = kwh * reading.unit_price
    if abs(kwh - reading.electricity_kwh) > TOLERANCE:
        raise HTTPException(status_code=409, detail="电量与起止度不符")
    if abs(fee - reading.electricity_fee) > TOLERANCE:
        raise HTTPException(status_code=409, detail="电费与电量乘单价不符")

    reading.sealed = True
    reading.sealed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(reading)
    return reading


@router.get("/{reading_id}/reconciliation", response_model=ReconciliationOut)
def get_reconciliation(
    reading_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    reading = _get_reading_or_404(db, reading_id)
    allocated_feed_kg = (
        db.query(func.coalesce(func.sum(FeedEvent.amount_kg), 0.0))
        .join(FeedAllocation, FeedAllocation.feed_event_id == FeedEvent.id)
        .filter(FeedAllocation.meter_reading_id == reading_id)
        .scalar()
        or 0.0
    )
    return ReconciliationOut(
        pond_id=reading.pond_id,
        reading_id=reading.id,
        reading_date=reading.reading_date,
        electricity_kwh=reading.electricity_kwh,
        electricity_fee=reading.electricity_fee,
        allocated_feed_kg=float(allocated_feed_kg),
        allocation_count=len(reading.allocations),
        sealed=reading.sealed,
    )
