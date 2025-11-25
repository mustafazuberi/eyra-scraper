from fastapi import Response
from fastapi.responses import JSONResponse
from typing import Optional, TypeVar
from constants import HTTP_STATUS, ERROR_CODES

T = TypeVar("T")

def create_success_response(
    data: T,
    message: Optional[str] = None,
    status_code: int = HTTP_STATUS["OK"],
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": True,
            "data": data,
            "message": message,
        },
    )


def create_error_response(
    code: str,
    message: str,
    status_code: int = HTTP_STATUS["BAD_REQUEST"],
    details: Optional[dict] = None,
) -> JSONResponse:
    error_payload = {
        "success": False,
        "error": {
            "code": code,
            "message": message,
        },
    }
    
    if details:
        error_payload["error"]["details"] = details
    
    return JSONResponse(
        status_code=status_code,
        content=error_payload,
    )
