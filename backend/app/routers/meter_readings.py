from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.feed_event import FeedEvent
from app.models.meter_reading import MeterReading
from app.models.pond import Pond
from app.models.reading_allocation import ReadingAllocation
from app.models.user import User
from app.schemas.meter_reading import (
    AllocationCreate,
    MeterReadingCreate,
    MeterReadingOut,
    ReadingReconciliation,
)

router = APIRouter(prefix="/api/meter-readings", tags=["meter-readings"])

# 封抄校验允许的浮点误差
TOLERANCE = 0.01


@router.get("", response_model=List[MeterReadingOut])
def list_readings(
    pond_id: Optional[int] = Query(None, alias="pondId"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(MeterReading)
    if pond_id is not None:
        q = q.filter(MeterReading.pond_id == pond_id)
    return q.order_by(MeterReading.read_date.desc(), MeterReading.id.desc()).all()


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
        read_date=payload.read_date,
        start_kwh=payload.start_kwh,
        end_kwh=payload.end_kwh,
        unit_price=payload.unit_price,
    )
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="同塘同日抄见已存在")
    db.refresh(item)
    return item


@router.delete("/{reading_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reading(
    reading_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    item = db.query(MeterReading).filter(MeterReading.id == reading_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="抄见不存在")
    if item.sealed:
        raise HTTPException(status_code=409, detail="已封抄见不能删除")
    db.delete(item)
    db.commit()


@router.post(
    "/allocations",
    response_model=MeterReadingOut,
    status_code=status.HTTP_201_CREATED,
)
def attach_allocation(
    payload: AllocationCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    reading = (
        db.query(MeterReading).filter(MeterReading.id == payload.reading_id).first()
    )
    if not reading:
        raise HTTPException(status_code=404, detail="抄见不存在")
    if reading.sealed:
        raise HTTPException(status_code=409, detail="抄见已封，不能再挂投喂")

    event = db.query(FeedEvent).filter(FeedEvent.id == payload.feed_event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="投喂记录不存在")
    # 投喂须属同塘
    if event.pond_id != reading.pond_id:
        raise HTTPException(status_code=400, detail="投喂记录不属于该塘口")

    exists = (
        db.query(ReadingAllocation)
        .filter(ReadingAllocation.feed_event_id == payload.feed_event_id)
        .first()
    )
    if exists:
        # 一笔投喂只能挂一张未封抄见
        raise HTTPException(status_code=409, detail="该投喂已挂在抄见上，一笔投喂只能挂一张抄见")

    item = ReadingAllocation(
        reading_id=payload.reading_id,
        feed_event_id=payload.feed_event_id,
    )
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="该投喂已挂在抄见上，一笔投喂只能挂一张抄见")
    db.refresh(reading)
    return reading


@router.delete(
    "/{reading_id}/allocations/{feed_event_id}",
    response_model=MeterReadingOut,
)
def detach_allocation(
    reading_id: int,
    feed_event_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    reading = db.query(MeterReading).filter(MeterReading.id == reading_id).first()
    if not reading:
        raise HTTPException(status_code=404, detail="抄见不存在")
    if reading.sealed:
        raise HTTPException(status_code=409, detail="抄见已封，不能摘除投喂")

    item = (
        db.query(ReadingAllocation)
        .filter(
            ReadingAllocation.reading_id == reading_id,
            ReadingAllocation.feed_event_id == feed_event_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="该投喂未挂在此抄见上")
    db.delete(item)
    db.commit()
    db.refresh(reading)
    return reading


@router.post("/{reading_id}/seal", response_model=MeterReadingOut)
def seal_reading(
    reading_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    reading = db.query(MeterReading).filter(MeterReading.id == reading_id).first()
    if not reading:
        raise HTTPException(status_code=404, detail="抄见不存在")
    if reading.sealed:
        raise HTTPException(status_code=409, detail="抄见已封")

    allocations = (
        db.query(ReadingAllocation)
        .filter(ReadingAllocation.reading_id == reading_id)
        .all()
    )
    # 至少挂两笔投喂
    if len(allocations) < 2:
        raise HTTPException(status_code=409, detail="至少挂两笔投喂才能封抄")

    # 电量 = 止度 − 起度；电费 = 电量 × 单价（误差不超过 0.01）
    kwh = reading.end_kwh - reading.start_kwh
    fee = kwh * reading.unit_price
    if abs(reading.kwh_used - kwh) > TOLERANCE:
        raise HTTPException(status_code=409, detail="电量与起止度不符")
    if abs(reading.fee - fee) > TOLERANCE:
        raise HTTPException(status_code=409, detail="电费与电量乘单价不符")

    reading.sealed = True
    db.commit()
    db.refresh(reading)
    return reading


@router.get("/reconciliation", response_model=List[ReadingReconciliation])
def reconcile_pond(
    pond_id: int = Query(..., alias="pondId"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """对账：返回该塘每张抄见的电费与所挂投喂千克合计。"""
    pond = db.query(Pond).filter(Pond.id == pond_id).first()
    if not pond:
        raise HTTPException(status_code=404, detail="塘口不存在")

    readings = (
        db.query(MeterReading)
        .filter(MeterReading.pond_id == pond_id)
        .order_by(MeterReading.read_date.desc(), MeterReading.id.desc())
        .all()
    )
    result: List[ReadingReconciliation] = []
    for r in readings:
        allocated_kg = (
            db.query(func.coalesce(func.sum(FeedEvent.amount_kg), 0.0))
            .join(ReadingAllocation, ReadingAllocation.feed_event_id == FeedEvent.id)
            .filter(ReadingAllocation.reading_id == r.id)
            .scalar()
            or 0.0
        )
        result.append(
            ReadingReconciliation(
                pond_id=r.pond_id,
                reading_id=r.id,
                sealed=r.sealed,
                kwh_used=r.kwh_used,
                fee=r.fee,
                allocated_count=len(r.allocations),
                allocated_feed_kg=round(float(allocated_kg), 2),
            )
        )
    return result
