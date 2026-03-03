"""
Unit tests for middleware.
Tests for issue #1: Add comprehensive validation system
"""
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from middleware import (
    RequestValidationMiddleware,
    SecurityHeadersMiddleware,
    RateLimitMiddleware
)


@pytest.fixture
def app():
    """Create a test FastAPI application."""
    app = FastAPI()
    
    @app.get("/test")
    async def test_endpoint():
        return {"message": "success"}
    
    @app.post("/test")
    async def test_post_endpoint(data: dict):
        return {"message": "success", "data": data}
    
    return app


class TestRequestValidationMiddleware:
    """Test cases for request validation middleware."""
    
    def test_get_request_passes(self, app):
        """Test that GET requests pass validation."""
        app.add_middleware(RequestValidationMiddleware)
        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200
    
    def test_post_with_json_content_type(self, app):
        """Test that POST with JSON content type passes."""
        app.add_middleware(RequestValidationMiddleware)
        client = TestClient(app)
        response = client.post("/test", json={"key": "value"})
        assert response.status_code == 200
    
    def test_post_without_content_type_fails(self, app):
        """Test that POST without proper content type fails."""
        app.add_middleware(RequestValidationMiddleware)
        client = TestClient(app)
        response = client.post(
            "/test",
            data="plain text",
            headers={"Content-Type": "text/plain"}
        )
        assert response.status_code == 415
    
    def test_process_time_header_added(self, app):
        """Test that X-Process-Time header is added."""
        app.add_middleware(RequestValidationMiddleware)
        client = TestClient(app)
        response = client.get("/test")
        assert "X-Process-Time" in response.headers


class TestSecurityHeadersMiddleware:
    """Test cases for security headers middleware."""
    
    def test_security_headers_added(self, app):
        """Test that security headers are added to response."""
        app.add_middleware(SecurityHeadersMiddleware)
        client = TestClient(app)
        response = client.get("/test")
        
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-XSS-Protection"] == "1; mode=block"
        assert "Strict-Transport-Security" in response.headers
        assert "Content-Security-Policy" in response.headers
    
    def test_hsts_header_format(self, app):
        """Test that HSTS header has correct format."""
        app.add_middleware(SecurityHeadersMiddleware)
        client = TestClient(app)
        response = client.get("/test")
        
        hsts = response.headers["Strict-Transport-Security"]
        assert "max-age=" in hsts
        assert "includeSubDomains" in hsts
    
    def test_csp_header_present(self, app):
        """Test that CSP header is present."""
        app.add_middleware(SecurityHeadersMiddleware)
        client = TestClient(app)
        response = client.get("/test")
        
        assert "Content-Security-Policy" in response.headers
        assert "default-src" in response.headers["Content-Security-Policy"]


class TestRateLimitMiddleware:
    """Test cases for rate limit middleware."""
    
    def test_requests_within_limit(self, app):
        """Test that requests within limit are allowed."""
        app.add_middleware(RateLimitMiddleware, max_requests=10, window_seconds=60)
        client = TestClient(app)
        
        for _ in range(5):
            response = client.get("/test")
            assert response.status_code == 200
    
    def test_rate_limit_exceeded(self, app):
        """Test that rate limit is enforced."""
        app.add_middleware(RateLimitMiddleware, max_requests=3, window_seconds=60)
        client = TestClient(app)
        
        # Make requests up to limit
        for _ in range(3):
            response = client.get("/test")
            assert response.status_code == 200
        
        # Next request should be rate limited
        response = client.get("/test")
        assert response.status_code == 429
    
    def test_rate_limit_error_message(self, app):
        """Test that rate limit error has proper message."""
        app.add_middleware(RateLimitMiddleware, max_requests=1, window_seconds=60)
        client = TestClient(app)
        
        # First request succeeds
        client.get("/test")
        
        # Second request fails with proper error
        response = client.get("/test")
        assert response.status_code == 429
        data = response.json()
        assert "error" in data
        assert "Rate limit exceeded" in data["error"]["message"]


class TestMiddlewareIntegration:
    """Integration tests for multiple middleware."""
    
    def test_multiple_middleware_stack(self, app):
        """Test that multiple middleware work together."""
        app.add_middleware(SecurityHeadersMiddleware)
        app.add_middleware(RequestValidationMiddleware)
        app.add_middleware(RateLimitMiddleware, max_requests=10, window_seconds=60)
        
        client = TestClient(app)
        response = client.get("/test")
        
        # Check all middleware effects
        assert response.status_code == 200
        assert "X-Process-Time" in response.headers
        assert "X-Content-Type-Options" in response.headers
    
    def test_middleware_order_matters(self, app):
        """Test that middleware order affects behavior."""
        # Add rate limit first, then validation
        app.add_middleware(RequestValidationMiddleware)
        app.add_middleware(RateLimitMiddleware, max_requests=1, window_seconds=60)
        
        client = TestClient(app)
        
        # First request succeeds
        response = client.get("/test")
        assert response.status_code == 200
        
        # Second request is rate limited
        response = client.get("/test")
        assert response.status_code == 429
