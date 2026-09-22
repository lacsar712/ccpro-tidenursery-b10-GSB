from sqlalchemy import Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FeedAllocation(Base):
    """把一张未封抄见的电费分摊到一笔投喂上。

    一笔投喂只能挂一张抄见（unique feed_event_id）。
    """

    __tablename__ = "feed_allocations"
    __table_args__ = (
        UniqueConstraint("meter_reading_id", "feed_event_id", name="uq_reading_feed"),
        UniqueConstraint("feed_event_id", name="uq_feed_event_allocation"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    meter_reading_id: Mapped[int] = mapped_column(
        ForeignKey("meter_readings.id"), nullable=False, index=True
    )
    feed_event_id: Mapped[int] = mapped_column(
        ForeignKey("feed_events.id"), nullable=False, index=True
    )

    meter_reading: Mapped["MeterReading"] = relationship(
        "MeterReading", back_populates="allocations"
    )
    feed_event: Mapped["FeedEvent"] = relationship(
        "FeedEvent", back_populates="allocations"
    )
