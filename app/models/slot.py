from sqlalchemy import Column, Integer, String, DECIMAL, DateTime, ForeignKey, Enum, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
import enum
from app.db.database import Base

class SlotStatus(enum.Enum):
    AVAILABLE = "AVAILABLE"
    BOOKED = "BOOKED"
    IN_USE = "IN_USE"
    LOCKED = "LOCKED"
    OFFLINE = "OFFLINE"

class ChargerType(enum.Enum):
    CCS2 = "CCS2"
    CHAdeMO = "CHAdeMO"
    TYPE2 = "TYPE2"
    BHARAT_AC = "BHARAT_AC"
    BHARAT_DC = "BHARAT_DC"

class Slot(Base):
    __tablename__ = "slots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    station_id = Column(UUID(as_uuid=True), ForeignKey("stations.id", ondelete="CASCADE"), nullable=False)
    slot_number = Column(Integer, nullable=False)
    charger_type = Column(Enum(ChargerType), nullable=False)
    power_kw = Column(DECIMAL(6, 1), nullable=False)
    status = Column(Enum(SlotStatus), nullable=False, default=SlotStatus.AVAILABLE)
    fault_code = Column(String(50))
    locked_by_user = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    locked_until = Column(DateTime(timezone=True))
    ocpp_connector_id = Column(Integer)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    station = relationship("Station", back_populates="slots")
