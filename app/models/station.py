from sqlalchemy import Column, String, Integer, DECIMAL, Boolean, DateTime, ForeignKey, func, text, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship
import uuid
import enum
from app.db.database import Base
from geoalchemy2 import Geography

class ChargingNetwork(enum.Enum):
    TATA_POWER = "TATA_POWER"
    CHARGE_ZONE = "CHARGE_ZONE"
    ATHER_GRID = "ATHER_GRID"
    STATIQ = "STATIQ"
    BPCL_PULSE = "BPCL_PULSE"
    EESL = "EESL"
    INDEPENDENT = "INDEPENDENT"

from sqlalchemy import Table
station_managers = Table(
    'station_managers', Base.metadata,
    Column('user_id', UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    Column('station_id', UUID(as_uuid=True), ForeignKey('stations.id', ondelete='CASCADE'), primary_key=True)
)

class Station(Base):
    __tablename__ = "stations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    network = Column(Enum(ChargingNetwork), nullable=False)
    location = Column(Geography(geometry_type='POINT', srid=4326), nullable=False)
    address = Column(JSONB, nullable=False)
    operating_hours = Column(JSONB, nullable=False)
    amenities = Column(ARRAY(String), server_default='{}')
    price_per_unit = Column(DECIMAL(10, 2))
    price_per_hour = Column(DECIMAL(10, 2))
    is_active = Column(Boolean, nullable=False, default=True)
    total_slots = Column(Integer, nullable=False, default=0)
    available_slots = Column(Integer, nullable=False, default=0)
    avg_rating = Column(DECIMAL(3, 2), default=0.00)
    total_reviews = Column(Integer, default=0)
    last_heartbeat = Column(DateTime(timezone=True))
    admin_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    ocpp_station_id = Column(String(50), unique=True)

    slots = relationship("Slot", back_populates="station", cascade="all, delete-orphan")
