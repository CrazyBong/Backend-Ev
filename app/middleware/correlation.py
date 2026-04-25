import uuid
import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Prefer existing X-Request-ID if provided by proxy/client, else generate
        correlation_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        
        # Attach to request state for access in routers/services
        request.state.correlation_id = correlation_id
        
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Inject into response headers
        response.headers["X-Request-ID"] = correlation_id
        response.headers["X-Process-Time"] = str(process_time)
        
        return response
