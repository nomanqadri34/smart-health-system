"""
Centralized error handling for Smart Health API.
Fixes issue #2: Improve error handling and logging
"""
import logging
from typing import Dict, Any, Optional
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class APIError(Exception):
    """Base exception for API errors."""
    
    def __init__(self, message: str, status_code: int = 500, details: Optional[Dict] = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(APIError):
    """Exception for validation errors."""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, status_code=400, details=details)


class DatabaseError(APIError):
    """Exception for database errors."""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, status_code=500, details=details)


class AuthenticationError(APIError):
    """Exception for authentication errors."""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, status_code=401, details=details)


class NotFoundError(APIError):
    """Exception for resource not found errors."""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, status_code=404, details=details)


def create_error_response(
    status_code: int,
    message: str,
    details: Optional[Dict] = None,
    error_code: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a standardized error response.
    
    Args:
        status_code: HTTP status code
        message: Error message
        details: Additional error details
        error_code: Application-specific error code
        
    Returns:
        Dictionary with error response structure
    """
    response = {
        "error": {
            "message": message,
            "status_code": status_code
        }
    }
    
    if error_code:
        response["error"]["code"] = error_code
    
    if details:
        response["error"]["details"] = details
    
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
    logger.error(
        f"API Error: {exc.message}",
        extra={
            "status_code": exc.status_code,
            "path": request.url.path,
            "method": request.method,
            "details": exc.details
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=create_error_response(
            status_code=exc.status_code,
            message=exc.message,
            details=exc.details
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
    logger.warning(
        f"Validation Error: {str(exc)}",
        extra={
            "path": request.url.path,
            "method": request.method
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=create_error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message="Validation error",
            details={"validation_errors": str(exc)}
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
    logger.exception(
        f"Unhandled Exception: {str(exc)}",
        extra={
            "path": request.url.path,
            "method": request.method
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=create_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Internal server error",
            error_code="INTERNAL_ERROR"
        )
    )


def log_request_info(request: Request, additional_info: Optional[Dict] = None):
    """
    Log request information for debugging.
    
    Args:
        request: FastAPI request object
        additional_info: Additional information to log
    """
    log_data = {
        "method": request.method,
        "path": request.url.path,
        "client_host": request.client.host if request.client else "unknown"
    }
    
    if additional_info:
        log_data.update(additional_info)
    
    logger.info("Request received", extra=log_data)
