import razorpay
from app.config import settings

# Initialize razorpay client instance
razorpay_client = razorpay.Client(
    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
)
