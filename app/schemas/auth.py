from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any
import uuid

class UserCreate(BaseModel):
    phone: str = Field(..., max_length=20)
    name: Optional[str] = None
    email: Optional[str] = None

class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    vehicle_type: Optional[str] = None

class UserResponse(BaseModel):
    id: uuid.UUID
    phone: str
    name: Optional[str]
    email: Optional[str]
    role: str
    is_active: bool
    
    model_config = ConfigDict(from_attributes=True)

class SendOTPRequest(BaseModel):
    phone: str = Field(..., description="Phone number in E.164 format, e.g. +919876543210", max_length=20)

class SendOTPResponse(BaseModel):
    message: str
    expires_in_seconds: int
    phone: str
    dev_otp: Optional[str] = None

class VerifyOTPRequest(BaseModel):
    phone: str = Field(..., description="Phone number associated with the OTP")
    otp: str = Field(..., description="6-digit OTP code", min_length=6, max_length=6)

class TokenPayload(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    access_token_expires_in: int
    refresh_token_expires_in: int
    user: Dict[str, Any]

class RefreshTokenRequest(BaseModel):
    refresh_token: str
