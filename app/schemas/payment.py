from pydantic import BaseModel, ConfigDict
from uuid import UUID

class PaymentVerifyRequest(BaseModel):
    booking_id: UUID
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str

    model_config = ConfigDict(from_attributes=True)

class PaymentVerifyResponse(BaseModel):
    status: str
    message: str

    model_config = ConfigDict(from_attributes=True)
