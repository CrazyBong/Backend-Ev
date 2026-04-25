from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.schemas.payment import PaymentVerifyRequest, PaymentVerifyResponse
from app.services.payment_service import (
    verify_razorpay_signature,
    verify_webhook_signature,
    confirm_booking_by_order,
)

router = APIRouter()

@router.post("/verify")
async def verify_payment(
    body: PaymentVerifyRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    is_valid = verify_razorpay_signature(
        body.razorpay_order_id,
        body.razorpay_payment_id,
        body.razorpay_signature,
    )
    if not is_valid:
        raise HTTPException(
            status_code=422,
            detail={"code": "PAYMENT_VERIFICATION_FAILED"}
        )

    # In a fully concurrent environment, webhook might beat the client to confirmation.
    # Therefore, confirm_booking_after_payment is idempotent.
    await confirm_booking_by_order(
        razorpay_order_id=body.razorpay_order_id,
        payment_id=body.razorpay_payment_id,
        db=db,
    )
    return {"data": {"status": "SUCCESS"}}

@router.post("/webhook")
async def razorpay_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    signature = request.headers.get("X-Razorpay-Signature")
    if not signature:
        raise HTTPException(status_code=400, detail={"code": "MISSING_SIGNATURE"})

    payload_body = await request.body()
    if not verify_webhook_signature(payload_body, signature):
        raise HTTPException(status_code=422, detail={"code": "INVALID_SIGNATURE"})

    import json
    try:
        data = json.loads(payload_body)
    except json.JSONDecodeError:
        raise dict()

    event = data.get("event")
    if event == "payment.captured":
        # Extract notes mapping
        try:
            payment_entity = data["payload"]["payment"]["entity"]
            order_id = payment_entity["order_id"]
            payment_id = payment_entity["id"]
        except KeyError:
            return {"status": "ignored"}
        
        await confirm_booking_by_order(
            razorpay_order_id=order_id,
            payment_id=payment_id,
            db=db,
        )


    return {"status": "ok"}
