from sqlalchemy import Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ReadingAllocation(Base):
    __tablename__ = "reading_allocations"
    __table_args__ = (
        UniqueConstraint("feed_event_id", name="uq_feed_event_reading"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    reading_id: Mapped[int] = mapped_column(
        ForeignKey("meter_readings.id"), nullable=False, index=True
    )
    feed_event_id: Mapped[int] = mapped_column(
        ForeignKey("feed_events.id"), nullable=False, index=True
    )

    reading: Mapped["MeterReading"] = relationship(
        "MeterReading", back_populates="allocations"
    )
    feed_event: Mapped["FeedEvent"] = relationship("FeedEvent")
