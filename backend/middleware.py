"""
Middleware for request validation and security.
Part of issue #1: Add comprehensive validation system
"""
import time
import logging
from typing import Callable
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


logger = logging.getLogger(__name__)


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """Middleware to validate incoming requests."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Validate request before processing.
        
        Args:
            request: Incoming request
            call_next: Next middleware/handler
            
        Returns:
            Response from next handler or error response
        """
        # Log request
        start_time = time.time()
        logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={"client": request.client.host if request.client else "unknown"}
        )
        
        # Validate content type for POST/PUT requests
        if request.method in ["POST", "PUT", "PATCH"]:
            content_type = request.headers.get("content-type", "")
            if not content_type.startswith("application/json"):
                return JSONResponse(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    content={
                        "error": {
                            "message": "Content-Type must be application/json",
                            "status_code": 415
                        }
                    }
                )
        
        # Process request
        try:
            response = await call_next(request)
            
            # Log response
            process_time = time.time() - start_time
            logger.info(
                f"Request completed: {request.method} {request.url.path}",
                extra={
                    "status_code": response.status_code,
                    "process_time": f"{process_time:.3f}s"
                }
            )
            
            # Add custom headers
            response.headers["X-Process-Time"] = f"{process_time:.3f}"
            
            return response
            
        except Exception as e:
            logger.exception(f"Request failed: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": {
                        "message": "Internal server error",
                        "status_code": 500
                    }
                }
            )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to responses."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Add security headers to response.
        
        Args:
            request: Incoming request
            call_next: Next middleware/handler
            
        Returns:
            Response with security headers
        """
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple rate limiting middleware."""
    
    def __init__(self, app, max_requests: int = 60, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = {}  # client_ip -> [(timestamp, count)]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Check rate limit before processing request.
        
        Args:
            request: Incoming request
            call_next: Next middleware/handler
            
        Returns:
            Response or rate limit error
        """
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()
        
        # Clean old entries
        if client_ip in self.requests:
            self.requests[client_ip] = [
                (ts, count) for ts, count in self.requests[client_ip]
                if current_time - ts < self.window_seconds
            ]
        
        # Check rate limit
        if client_ip in self.requests:
            total_requests = sum(count for _, count in self.requests[client_ip])
            if total_requests >= self.max_requests:
                logger.warning(f"Rate limit exceeded for {client_ip}")
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "error": {
                            "message": "Rate limit exceeded. Please try again later.",
                            "status_code": 429
                        }
                    }
                )
        
        # Record request
        if client_ip not in self.requests:
            self.requests[client_ip] = []
        self.requests[client_ip].append((current_time, 1))
        
        return await call_next(request)
