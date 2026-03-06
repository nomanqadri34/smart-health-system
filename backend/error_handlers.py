"""
Centralized error handling for Smart Health API.
Fixes issue #2: Enhanced error handling and logging system
"""
import logging
import traceback
from typing import Dict, Any, Optional
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from datetime import datetime


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class APIError(Exception):
    """Base exception for API errors."""
    
    def __init__(self, message: str, status_code: int = 500, details: Optional[Dict] = None, error_code: Optional[str] = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        self.error_code = error_code
        self.timestamp = datetime.utcnow().isoformat()
        super().__init__(self.message)


class ValidationError(APIError):
    """Exception for validation errors."""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, status_code=400, details=details, error_code="VALIDATION_ERROR")


class DatabaseError(APIError):
    """Exception for database errors."""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, status_code=500, details=details, error_code="DATABASE_ERROR")


class AuthenticationError(APIError):
    """Exception for authentication errors."""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, status_code=401, details=details, error_code="AUTH_ERROR")


class AuthorizationError(APIError):
    """Exception for authorization errors."""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, status_code=403, details=details, error_code="AUTHORIZATION_ERROR")


class NotFoundError(APIError):
    """Exception for resource not found errors."""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, status_code=404, details=details, error_code="NOT_FOUND")


class ConflictError(APIError):
    """Exception for resource conflict errors."""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, status_code=409, details=details, error_code="CONFLICT")


class RateLimitError(APIError):
    """Exception for rate limit errors."""
    
    def __init__(self, message: str = "Rate limit exceeded", details: Optional[Dict] = None):
        super().__init__(message, status_code=429, details=details, error_code="RATE_LIMIT_EXCEEDED")


def create_error_response(
    status_code: int,
    message: str,
    details: Optional[Dict] = None,
    error_code: Optional[str] = None,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a standardized error response.
    
    Args:
        status_code: HTTP status code
        message: Error message
        details: Additional error details
        error_code: Application-specific error code
        request_id: Unique request identifier
        
    Returns:
        Dictionary with error response structure
    """
    response = {
        "error": {
            "message": message,
            "status_code": status_code,
            "timestamp": datetime.utcnow().isoformat()
        }
    }
    
    if error_code:
        response["error"]["code"] = error_code
    
    if details:
        response["error"]["details"] = details
    
    if request_id:
        response["error"]["request_id"] = request_id
    
    return response


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """
    Handle custom API errors.
    
    Args:
        request: FastAPI request object
        exc: API error exception
        
    Returns:
        JSON response with error details
    """
    request_id = request.headers.get("X-Request-ID", "unknown")
    
    logger.error(
        f"API Error: {exc.message}",
        extra={
            "status_code": exc.status_code,
            "error_code": exc.error_code,
            "path": request.url.path,
            "method": request.method,
            "request_id": request_id,
            "details": exc.details
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=create_error_response(
            status_code=exc.status_code,
            message=exc.message,
            details=exc.details,
            error_code=exc.error_code,
            request_id=request_id
        )
    )


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle validation exceptions.
    
    Args:
        request: FastAPI request object
        exc: Validation exception
        
    Returns:
        JSON response with validation error details
    """
    request_id = request.headers.get("X-Request-ID", "unknown")
    
    logger.warning(
        f"Validation Error: {str(exc)}",
        extra={
            "path": request.url.path,
            "method": request.method,
            "request_id": request_id
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=create_error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message="Validation error",
            details={"validation_errors": str(exc)},
            error_code="VALIDATION_FAILED",
            request_id=request_id
        )
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle general exceptions.
    
    Args:
        request: FastAPI request object
        exc: General exception
        
    Returns:
        JSON response with error details
    """
    request_id = request.headers.get("X-Request-ID", "unknown")
    
    # Log full traceback for debugging
    logger.exception(
        f"Unhandled Exception: {str(exc)}",
        extra={
            "path": request.url.path,
            "method": request.method,
            "request_id": request_id,
            "traceback": traceback.format_exc()
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=create_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Internal server error",
            error_code="INTERNAL_ERROR",
            request_id=request_id
        )
    )


def log_request_info(request: Request, additional_info: Optional[Dict] = None):
    """
    Log request information for debugging.
    
    Args:
        request: FastAPI request object
        additional_info: Additional information to log
    """
    request_id = request.headers.get("X-Request-ID", "unknown")
    
    log_data = {
        "method": request.method,
        "path": request.url.path,
        "client_host": request.client.host if request.client else "unknown",
        "request_id": request_id,
        "user_agent": request.headers.get("User-Agent", "unknown")
    }
    
    if additional_info:
        log_data.update(additional_info)
    
    logger.info("Request received", extra=log_data)


def log_response_info(request: Request, status_code: int, process_time: float):
    """
    Log response information.
    
    Args:
        request: FastAPI request object
        status_code: HTTP status code
        process_time: Request processing time in seconds
    """
    request_id = request.headers.get("X-Request-ID", "unknown")
    
    logger.info(
        "Request completed",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": status_code,
            "process_time": f"{process_time:.3f}s",
            "request_id": request_id
        }
    )
