from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MeterReadingCreate(BaseModel):
    pond_id: int = Field(..., alias="pondId")
    reading_date: date = Field(..., alias="readingDate")
    start_kwh: float = Field(..., alias="startKwh")
    end_kwh: float = Field(..., alias="endKwh")
    unit_price: float = Field(..., gt=0, alias="unitPrice")

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def validate_readings(self):
        if self.end_kwh <= self.start_kwh:
            raise ValueError("止度必须大于起度")
        return self


class AllocationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    meter_reading_id: int = Field(serialization_alias="meterReadingId")
    feed_event_id: int = Field(serialization_alias="feedEventId")


class MeterReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    pond_id: int = Field(serialization_alias="pondId")
    reading_date: date = Field(serialization_alias="readingDate")
    start_kwh: float = Field(serialization_alias="startKwh")
    end_kwh: float = Field(serialization_alias="endKwh")
    unit_price: float = Field(serialization_alias="unitPrice")
    sealed: bool
    sealed_at: Optional[datetime] = Field(None, serialization_alias="sealedAt")
    electricity_kwh: float = Field(serialization_alias="electricityKwh")
    electricity_fee: float = Field(serialization_alias="electricityFee")
    allocation_count: int = Field(serialization_alias="allocationCount")
    allocations: List[AllocationOut] = []


class AllocationCreate(BaseModel):
    feed_event_id: int = Field(..., alias="feedEventId")

    model_config = ConfigDict(populate_by_name=True)


class ReconciliationOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    pond_id: int = Field(serialization_alias="pondId")
    reading_id: int = Field(serialization_alias="readingId")
    reading_date: date = Field(serialization_alias="readingDate")
    electricity_kwh: float = Field(serialization_alias="electricityKwh")
    electricity_fee: float = Field(serialization_alias="electricityFee")
    allocated_feed_kg: float = Field(serialization_alias="allocatedFeedKg")
    allocation_count: int = Field(serialization_alias="allocationCount")
    sealed: bool
