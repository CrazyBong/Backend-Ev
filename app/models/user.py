from sqlalchemy import Column, String, Boolean, DateTime, Enum, func
from sqlalchemy.dialects.postgresql import UUID
import enum
import uuid
from app.db.database import Base

class UserRole(enum.Enum):
    user = "user"
    station_admin = "station_admin"
    super_admin = "super_admin"

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone = Column(String(20), nullable=False, unique=True)
    name = Column(String(100))
    email = Column(String(255), unique=True)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.user)
    vehicle_type = Column(String(100))
    # charger_type is an enum, we'll define it in a shared location or here
    preferred_connector = Column(String(50)) 
    expo_push_token = Column(String(255))
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
