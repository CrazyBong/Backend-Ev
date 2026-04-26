from sqlalchemy import Column, String, DECIMAL, DateTime, ForeignKey, Enum, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
import enum
from app.db.database import Base

class BookingStatus(enum.Enum):
    PENDING_PAYMENT = "PENDING_PAYMENT"
    CONFIRMED = "CONFIRMED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED_BY_USER = "CANCELLED_BY_USER"
    CANCELLED_BY_ADMIN = "CANCELLED_BY_ADMIN"
    CANCELLED_BY_SYSTEM = "CANCELLED_BY_SYSTEM"
    NO_SHOW = "NO_SHOW"
    REFUND_PENDING = "REFUND_PENDING"

class Booking(Base):
    __tablename__ = "bookings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    slot_id = Column(UUID(as_uuid=True), ForeignKey("slots.id"), nullable=False)
    station_id = Column(UUID(as_uuid=True), ForeignKey("stations.id"), nullable=False)
    status = Column(Enum(BookingStatus), nullable=False, default=BookingStatus.PENDING_PAYMENT)
    scheduled_start = Column(DateTime(timezone=True), nullable=False)
    scheduled_end = Column(DateTime(timezone=True), nullable=False)
    actual_start = Column(DateTime(timezone=True))
    actual_end = Column(DateTime(timezone=True))
    amount = Column(DECIMAL(10, 2), nullable=False)
    energy_consumed_kwh = Column(DECIMAL(8, 2))
    qr_code = Column(String(500))
    cancellation_reason = Column(String)
    idempotency_key = Column(String(36), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    user = relationship("User")
    slot = relationship("Slot")
    station = relationship("Station")
    payment = relationship("Payment", back_populates="booking", uselist=False)
