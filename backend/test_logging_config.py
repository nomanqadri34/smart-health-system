"""
Unit tests for logging configuration.
Tests for issue #2: Enhanced error handling and logging system
"""
import pytest
import logging
import json
from logging_config import (
    JSONFormatter,
    ColoredFormatter,
    setup_logging,
    get_logger,
    RequestLogger,
    DatabaseLogger
)


class TestJSONFormatter:
    """Test cases for JSON formatter."""
    
    def test_json_formatter_basic(self):
        """Test that JSON formatter produces valid JSON."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        formatted = formatter.format(record)
        data = json.loads(formatted)
        
        assert data["message"] == "Test message"
        assert data["level"] == "INFO"
        assert "timestamp" in data
    
    def test_json_formatter_with_extra_fields(self):
        """Test that JSON formatter includes extra fields."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.request_id = "req-123"
        record.user_id = "user-456"
        
        formatted = formatter.format(record)
        data = json.loads(formatted)
        
        assert data["request_id"] == "req-123"
        assert data["user_id"] == "user-456"
    
    def test_json_formatter_with_exception(self):
        """Test that JSON formatter includes exception info."""
        formatter = JSONFormatter()
        
        try:
            raise ValueError("Test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()
            
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="test.py",
                lineno=10,
                msg="Error occurred",
                args=(),
                exc_info=exc_info
            )
            
            formatted = formatter.format(record)
            data = json.loads(formatted)
            
            assert "exception" in data
            assert "ValueError" in data["exception"]


class TestColoredFormatter:
    """Test cases for colored formatter."""
    
    def test_colored_formatter_adds_colors(self):
        """Test that colored formatter adds ANSI color codes."""
        formatter = ColoredFormatter('%(levelname)s - %(message)s')
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        formatted = formatter.format(record)
        
        # Check for ANSI escape codes
        assert '\033[' in formatted
    
    def test_colored_formatter_different_levels(self):
        """Test that different log levels get different colors."""
        formatter = ColoredFormatter('%(levelname)s - %(message)s')
        
        levels = [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR]
        formatted_messages = []
        
        for level in levels:
            record = logging.LogRecord(
                name="test",
                level=level,
                pathname="test.py",
                lineno=10,
                msg="Test message",
                args=(),
                exc_info=None
            )
            formatted_messages.append(formatter.format(record))
        
        # Each level should have different formatting
        assert len(set(formatted_messages)) == len(levels)


class TestSetupLogging:
    """Test cases for logging setup."""
    
    def test_setup_logging_basic(self):
        """Test basic logging setup."""
        setup_logging(log_level="INFO")
        logger = logging.getLogger()
        
        assert logger.level == logging.INFO
        assert len(logger.handlers) > 0
    
    def test_setup_logging_with_file(self, tmp_path):
        """Test logging setup with file handler."""
        log_file = tmp_path / "test.log"
        setup_logging(log_level="DEBUG", log_file=str(log_file))
        
        logger = logging.getLogger()
        logger.info("Test message")
        
        assert log_file.exists()
        content = log_file.read_text()
        assert "Test message" in content
    
    def test_setup_logging_json_format(self):
        """Test logging setup with JSON format."""
        setup_logging(log_level="INFO", json_format=True)
        logger = logging.getLogger()
        
        # Check that JSON formatter is used
        assert len(logger.handlers) > 0
        handler = logger.handlers[0]
        assert isinstance(handler.formatter, JSONFormatter)


class TestGetLogger:
    """Test cases for get_logger function."""
    
    def test_get_logger_returns_logger(self):
        """Test that get_logger returns a logger instance."""
        logger = get_logger("test")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test"
    
    def test_get_logger_same_name_returns_same_instance(self):
        """Test that same name returns same logger instance."""
        logger1 = get_logger("test")
        logger2 = get_logger("test")
        assert logger1 is logger2


class TestRequestLogger:
    """Test cases for RequestLogger."""
    
    def test_request_logger_log_request(self):
        """Test logging HTTP request."""
        logger = logging.getLogger("test")
        request_logger = RequestLogger(logger)
        
        # Should not raise exception
        request_logger.log_request(
            method="GET",
            path="/api/test",
            status_code=200,
            process_time=0.123,
            request_id="req-123"
        )
    
    def test_request_logger_log_error(self):
        """Test logging HTTP request error."""
        logger = logging.getLogger("test")
        request_logger = RequestLogger(logger)
        
        error = ValueError("Test error")
        
        # Should not raise exception
        request_logger.log_error(
            method="POST",
            path="/api/test",
            error=error,
            request_id="req-123"
        )


class TestDatabaseLogger:
    """Test cases for DatabaseLogger."""
    
    def test_database_logger_log_query(self):
        """Test logging database query."""
        logger = logging.getLogger("test")
        db_logger = DatabaseLogger(logger)
        
        # Should not raise exception
        db_logger.log_query(
            query="SELECT * FROM users WHERE id = ?",
            params={"id": 1},
            execution_time=0.05
        )
    
    def test_database_logger_log_error(self):
        """Test logging database error."""
        logger = logging.getLogger("test")
        db_logger = DatabaseLogger(logger)
        
        error = Exception("Connection failed")
        
        # Should not raise exception
        db_logger.log_error(
            operation="connect",
            error=error
        )


class TestLoggingIntegration:
    """Integration tests for logging system."""
    
    def test_full_logging_workflow(self, tmp_path):
        """Test complete logging workflow."""
        log_file = tmp_path / "app.log"
        
        # Setup logging
        setup_logging(
            log_level="DEBUG",
            log_file=str(log_file),
            json_format=False
        )
        
        # Get logger and log messages
        logger = get_logger("test_app")
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        
        # Check log file
        assert log_file.exists()
        content = log_file.read_text()
        assert "Debug message" in content
        assert "Info message" in content
        assert "Warning message" in content
        assert "Error message" in content
    
    def test_request_and_database_logging(self, tmp_path):
        """Test request and database logging together."""
        log_file = tmp_path / "app.log"
        setup_logging(log_level="INFO", log_file=str(log_file))
        
        # Create loggers
        logger = get_logger("app")
        request_logger = RequestLogger(logger)
        db_logger = DatabaseLogger(logger)
        
        # Log request
        request_logger.log_request(
            method="GET",
            path="/api/users",
            status_code=200,
            process_time=0.15
        )
        
        # Log database query
        db_logger.log_query(
            query="SELECT * FROM users",
            execution_time=0.05
        )
        
        # Check log file
        content = log_file.read_text()
        assert "GET /api/users" in content
