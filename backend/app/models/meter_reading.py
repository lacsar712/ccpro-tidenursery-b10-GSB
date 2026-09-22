from datetime import date
from typing import List

from sqlalchemy import (
    Integer,
    Float,
    Date,
    Boolean,
    ForeignKey,
    UniqueConstraint,
    false,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MeterReading(Base):
    __tablename__ = "meter_readings"
    __table_args__ = (
        UniqueConstraint("pond_id", "read_date", name="uq_pond_read_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    pond_id: Mapped[int] = mapped_column(ForeignKey("ponds.id"), nullable=False, index=True)
    read_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    end_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    sealed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )

    pond: Mapped["Pond"] = relationship("Pond", back_populates="meter_readings")
    allocations: Mapped[List["ReadingAllocation"]] = relationship(
        "ReadingAllocation",
        back_populates="reading",
        cascade="all, delete-orphan",
    )

    @property
    def kwh_used(self) -> float:
        # 电量(kWh) = 止度 − 起度
        return round(self.end_kwh - self.start_kwh, 2)

    @property
    def fee(self) -> float:
        # 电费(元) = 电量 × 单价
        return round((self.end_kwh - self.start_kwh) * self.unit_price, 2)

    @property
    def feed_event_ids(self) -> List[int]:
        return [a.feed_event_id for a in self.allocations]
