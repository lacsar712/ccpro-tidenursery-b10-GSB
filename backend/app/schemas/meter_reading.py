from datetime import date
from typing import List

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MeterReadingCreate(BaseModel):
    pond_id: int = Field(..., alias="pondId")
    read_date: date = Field(..., alias="readDate")
    start_kwh: float = Field(..., ge=0, alias="startKwh")
    end_kwh: float = Field(..., ge=0, alias="endKwh")
    unit_price: float = Field(..., gt=0, alias="unitPrice")

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def validate_readings(self):
        # 止度必须大于起度
        if self.end_kwh <= self.start_kwh:
            raise ValueError("止度必须大于起度")
        return self


class MeterReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    pond_id: int = Field(serialization_alias="pondId")
    read_date: date = Field(serialization_alias="readDate")
    start_kwh: float = Field(serialization_alias="startKwh")
    end_kwh: float = Field(serialization_alias="endKwh")
    unit_price: float = Field(serialization_alias="unitPrice")
    sealed: bool
    kwh_used: float = Field(serialization_alias="kwhUsed")
    fee: float
    feed_event_ids: List[int] = Field(serialization_alias="feedEventIds")


class AllocationCreate(BaseModel):
    reading_id: int = Field(..., alias="readingId")
    feed_event_id: int = Field(..., alias="feedEventId")

    model_config = ConfigDict(populate_by_name=True)


class ReadingReconciliation(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    pond_id: int = Field(serialization_alias="pondId")
    reading_id: int = Field(serialization_alias="readingId")
    sealed: bool
    kwh_used: float = Field(serialization_alias="kwhUsed")
    fee: float
    allocated_count: int = Field(serialization_alias="allocatedCount")
    allocated_feed_kg: float = Field(serialization_alias="allocatedFeedKg")
