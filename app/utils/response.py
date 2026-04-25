"""
Standardized API response helpers.
All endpoints should use these wrappers to ensure consistent envelope format.
"""
from typing import Any, Optional


def success_response(
    data: Any = None,
    message: str = "Success",
    meta: Optional[dict] = None,
) -> dict:
    """
    Standard success envelope:
    {
        "success": true,
        "message": "...",
        "data": <payload>,
        "meta": { "page": 1, "total": 50, ... }   # optional
    }
    """
    response = {
        "success": True,
        "message": message,
    }
    if data is not None:
        response["data"] = data
    if meta:
        response["meta"] = meta
    return response


def error_response(
    code: str,
    message: str,
    details: Any = None,
) -> dict:
    """
    Standard error envelope:
    {
        "success": false,
        "error": { "code": "...", "message": "...", "details": ... }
    }
    """
    payload = {"code": code, "message": message}
    if details is not None:
        payload["details"] = details
    return {"success": False, "error": payload}
