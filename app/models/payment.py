from sqlalchemy import Column, String, DECIMAL, DateTime, ForeignKey, Enum, Boolean, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
import enum
from app.db.database import Base

class PaymentStatus(enum.Enum):
    CREATED = "CREATED"
    PENDING_WEBHOOK = "PENDING_WEBHOOK"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"

class Payment(Base):
    __tablename__ = "payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id = Column(UUID(as_uuid=True), ForeignKey("bookings.id"), nullable=False, unique=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    razorpay_order_id = Column(String(100), nullable=False, unique=True)
    razorpay_payment_id = Column(String(100), unique=True)
    status = Column(Enum(PaymentStatus), nullable=False, default=PaymentStatus.CREATED)
    amount = Column(DECIMAL(10, 2), nullable=False)
    refund_amount = Column(DECIMAL(10, 2), default=0.00)
    razorpay_refund_id = Column(String(100))
    webhook_verified = Column(Boolean, default=False)
    webhook_received_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    booking = relationship("Booking", back_populates="payment")
    user = relationship("User")
