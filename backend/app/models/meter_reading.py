from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import String, Integer, Float, ForeignKey, Date, Boolean, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MeterReading(Base):
    """按塘口登记的电表抄见。止度必须大于起度；同塘同日唯一。"""

    __tablename__ = "meter_readings"
    __table_args__ = (
        UniqueConstraint("pond_id", "reading_date", name="uq_pond_reading_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    pond_id: Mapped[int] = mapped_column(ForeignKey("ponds.id"), nullable=False, index=True)
    reading_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    end_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    sealed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sealed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    pond: Mapped["Pond"] = relationship("Pond", back_populates="meter_readings")
    allocations: Mapped[List["FeedAllocation"]] = relationship(
        "FeedAllocation", back_populates="meter_reading", cascade="all, delete-orphan"
    )

    @property
    def electricity_kwh(self) -> float:
        # 电量 = 止度 - 起度
        return self.end_kwh - self.start_kwh

    @property
    def electricity_fee(self) -> float:
        # 电费 = 电量 × 单价
        return self.electricity_kwh * self.unit_price

    @property
    def allocation_count(self) -> int:
        return len(self.allocations)
