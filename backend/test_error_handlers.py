"""
Unit tests for error handlers.
Tests for issue #2: Improve error handling and logging
"""
import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from error_handlers import (
    APIError,
    ValidationError,
    DatabaseError,
    AuthenticationError,
    NotFoundError,
    create_error_response,
    api_error_handler
)


class TestAPIErrors:
    """Test cases for custom API error classes."""
    
    def test_api_error_creation(self):
        """Test that APIError can be created with message and status code."""
        error = APIError("Test error", status_code=500)
        assert error.message == "Test error"
        assert error.status_code == 500
        assert error.details == {}
    
    def test_api_error_with_details(self):
        """Test that APIError can include additional details."""
        details = {"field": "email", "reason": "invalid format"}
        error = APIError("Validation failed", status_code=400, details=details)
        assert error.details == details
    
    def test_validation_error(self):
        """Test that ValidationError has correct status code."""
        error = ValidationError("Invalid input")
        assert error.status_code == 400
        assert "Invalid input" in error.message
    
    def test_database_error(self):
        """Test that DatabaseError has correct status code."""
        error = DatabaseError("Connection failed")
        assert error.status_code == 500
        assert "Connection failed" in error.message
    
    def test_authentication_error(self):
        """Test that AuthenticationError has correct status code."""
        error = AuthenticationError("Invalid credentials")
        assert error.status_code == 401
        assert "Invalid credentials" in error.message
    
    def test_not_found_error(self):
        """Test that NotFoundError has correct status code."""
        error = NotFoundError("Resource not found")
        assert error.status_code == 404
        assert "Resource not found" in error.message


class TestErrorResponse:
    """Test cases for error response creation."""
    
    def test_create_basic_error_response(self):
        """Test creating a basic error response."""
        response = create_error_response(400, "Bad request")
        assert response["error"]["message"] == "Bad request"
        assert response["error"]["status_code"] == 400
    
    def test_create_error_response_with_details(self):
        """Test creating error response with additional details."""
        details = {"field": "email", "issue": "required"}
        response = create_error_response(400, "Validation error", details=details)
        assert response["error"]["details"] == details
    
    def test_create_error_response_with_code(self):
        """Test creating error response with error code."""
        response = create_error_response(
            500,
            "Internal error",
            error_code="DB_CONNECTION_FAILED"
        )
        assert response["error"]["code"] == "DB_CONNECTION_FAILED"
    
    def test_error_response_structure(self):
        """Test that error response has correct structure."""
        response = create_error_response(404, "Not found")
        assert "error" in response
        assert "message" in response["error"]
        assert "status_code" in response["error"]


class TestErrorHandlerIntegration:
    """Integration tests for error handlers."""
    
    @pytest.mark.asyncio
    async def test_api_error_handler_response(self):
        """Test that API error handler returns correct response."""
        # Create a mock request
        class MockRequest:
            url = type('obj', (object,), {'path': '/test'})()
            method = "GET"
        
        request = MockRequest()
        error = ValidationError("Invalid input", details={"field": "email"})
        
        response = await api_error_handler(request, error)
        assert response.status_code == 400
    
    def test_validation_error_inheritance(self):
        """Test that ValidationError inherits from APIError."""
        error = ValidationError("Test")
        assert isinstance(error, APIError)
    
    def test_database_error_inheritance(self):
        """Test that DatabaseError inherits from APIError."""
        error = DatabaseError("Test")
        assert isinstance(error, APIError)
    
    def test_authentication_error_inheritance(self):
        """Test that AuthenticationError inherits from APIError."""
        error = AuthenticationError("Test")
        assert isinstance(error, APIError)
    
    def test_not_found_error_inheritance(self):
        """Test that NotFoundError inherits from APIError."""
        error = NotFoundError("Test")
        assert isinstance(error, APIError)


class TestErrorMessages:
    """Test cases for error message formatting."""
    
    def test_error_message_preserved(self):
        """Test that error messages are preserved correctly."""
        message = "This is a test error message"
        error = APIError(message)
        assert str(error) == message
    
    def test_error_details_accessible(self):
        """Test that error details are accessible."""
        details = {"key1": "value1", "key2": "value2"}
        error = APIError("Test", details=details)
        assert error.details["key1"] == "value1"
        assert error.details["key2"] == "value2"
    
    def test_empty_details_default(self):
        """Test that details default to empty dict."""
        error = APIError("Test")
        assert error.details == {}
        assert isinstance(error.details, dict)
