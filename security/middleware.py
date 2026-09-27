"""
FaultLens Security - Middleware & Information Masking
Sanitizes unhandled exception stack traces and applies OWASP security headers.
"""

import uuid
import logging
import traceback
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

# Configure internal secure logging
logger = logging.getLogger("faultlens.security")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


class InformationMaskingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        try:
            response = await call_next(request)

            # Apply Security Headers
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response.headers["X-FaultLens-Request-ID"] = request_id

            return response

        except Exception as exc:
            # Secure Internal Logging (full stack trace for SRE investigation)
            logger.error(f"[REQ-ID: {request_id}] Unhandled Server Exception: {str(exc)}\n{traceback.format_exc()}")

            # Masked External Client Response (No sensitive stack traces or schema leaks)
            masked_error = {
                "error": "Internal Processing Failure",
                "code": "ERR_INTERNAL_MASKED",
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "request_id": request_id,
                "message": "An unexpected error occurred. Internal security details have been masked and logged securely for audit."
            }

            headers = {
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "X-FaultLens-Request-ID": request_id
            }

            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=masked_error,
                headers=headers
            )
