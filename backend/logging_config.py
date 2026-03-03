"""
Logging configuration for Smart Health API.
Part of issue #2: Enhanced error handling and logging system
"""
import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional
import json
from datetime import datetime


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON.
        
        Args:
            record: Log record to format
            
        Returns:
            JSON-formatted log string
        """
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        
        if hasattr(record, "status_code"):
            log_data["status_code"] = record.status_code
        
        if hasattr(record, "process_time"):
            log_data["process_time"] = record.process_time
        
        return json.dumps(log_data)


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for console output."""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record with colors.
        
        Args:
            record: Log record to format
            
        Returns:
            Colored log string
        """
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        
        # Format the message
        formatted = super().format(record)
        
        # Add color
        return f"{color}{formatted}{reset}"


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    json_format: bool = False,
    colored_console: bool = True
) -> None:
    """
    Setup logging configuration.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (optional)
        json_format: Use JSON format for logs
        colored_console: Use colored output for console
    """
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Remove existing handlers
    root_logger.handlers = []
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    
    if json_format:
        console_formatter = JSONFormatter()
    elif colored_console:
        console_formatter = ColoredFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    else:
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file:
        # Create log directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Rotating file handler (10MB max, keep 5 backups)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(getattr(logging, log_level.upper()))
        
        if json_format:
            file_formatter = JSONFormatter()
        else:
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class RequestLogger:
    """Helper class for logging HTTP requests."""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
    
    def log_request(
        self,
        method: str,
        path: str,
        status_code: int,
        process_time: float,
        request_id: Optional[str] = None,
        user_id: Optional[str] = None
    ):
        """
        Log HTTP request.
        
        Args:
            method: HTTP method
            path: Request path
            status_code: Response status code
            process_time: Request processing time in seconds
            request_id: Unique request identifier
            user_id: User identifier (if authenticated)
        """
        extra = {
            "request_id": request_id,
            "user_id": user_id,
            "status_code": status_code,
            "process_time": f"{process_time:.3f}s"
        }
        
        self.logger.info(
            f"{method} {path} - {status_code} - {process_time:.3f}s",
            extra=extra
        )
    
    def log_error(
        self,
        method: str,
        path: str,
        error: Exception,
        request_id: Optional[str] = None
    ):
        """
        Log HTTP request error.
        
        Args:
            method: HTTP method
            path: Request path
            error: Exception that occurred
            request_id: Unique request identifier
        """
        extra = {
            "request_id": request_id,
            "error_type": type(error).__name__
        }
        
        self.logger.error(
            f"{method} {path} - Error: {str(error)}",
            extra=extra,
            exc_info=True
        )


class DatabaseLogger:
    """Helper class for logging database operations."""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
    
    def log_query(
        self,
        query: str,
        params: Optional[dict] = None,
        execution_time: Optional[float] = None
    ):
        """
        Log database query.
        
        Args:
            query: SQL query
            params: Query parameters
            execution_time: Query execution time in seconds
        """
        extra = {}
        if execution_time:
            extra["execution_time"] = f"{execution_time:.3f}s"
        
        self.logger.debug(
            f"Query: {query}",
            extra=extra
        )
    
    def log_error(self, operation: str, error: Exception):
        """
        Log database error.
        
        Args:
            operation: Database operation that failed
            error: Exception that occurred
        """
        self.logger.error(
            f"Database error during {operation}: {str(error)}",
            exc_info=True
        )
