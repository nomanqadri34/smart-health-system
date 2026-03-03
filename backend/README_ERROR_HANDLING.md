# Error Handling and Logging System Documentation

## Overview

This comprehensive error handling and logging system provides robust error management, structured logging, and monitoring capabilities for the Smart Health API.

## Components

### 1. Error Handlers (`error_handlers.py`)

Custom exception classes and error handling:

- **APIError**: Base exception class with status code, details, error code, and timestamp
- **ValidationError**: 400 - Input validation failures
- **DatabaseError**: 500 - Database operation failures
- **AuthenticationError**: 401 - Authentication failures
- **AuthorizationError**: 403 - Authorization/permission failures
- **NotFoundError**: 404 - Resource not found
- **ConflictError**: 409 - Resource conflicts (e.g., duplicate entries)
- **RateLimitError**: 429 - Rate limit exceeded

### 2. Logging Configuration (`logging_config.py`)

Advanced logging setup and formatters:

- **JSONFormatter**: Structured JSON logging for production
- **ColoredFormatter**: Colored console output for development
- **RequestLogger**: HTTP request/response logging
- **DatabaseLogger**: Database operation logging
- **Rotating file handler**: Automatic log rotation (10MB max, 5 backups)

## Usage Examples

### Raising Custom Errors

```python
from error_handlers import ValidationError, NotFoundError, DatabaseError

# Validation error
if not email:
    raise ValidationError(
        "Email is required",
        details={"field": "email", "constraint": "required"}
    )

# Not found error
user = get_user(user_id)
if not user:
    raise NotFoundError(
        f"User {user_id} not found",
        details={"user_id": user_id}
    )

# Database error
try:
    db.commit()
except Exception as e:
    raise DatabaseError(
        "Failed to save data",
        details={"operation": "commit", "error": str(e)}
    )
```

### Setting Up Logging

```python
from logging_config import setup_logging, get_logger

# Setup logging (call once at startup)
setup_logging(
    log_level="INFO",
    log_file="logs/app.log",
    json_format=True,  # Use JSON for production
    colored_console=True  # Use colors for development
)

# Get logger in your modules
logger = get_logger(__name__)

# Log messages
logger.info("Application started")
logger.warning("Low memory warning")
logger.error("Failed to connect to database")
```

### Request Logging

```python
from logging_config import RequestLogger, get_logger

logger = get_logger(__name__)
request_logger = RequestLogger(logger)

# Log successful request
request_logger.log_request(
    method="GET",
    path="/api/users",
    status_code=200,
    process_time=0.123,
    request_id="req-abc-123",
    user_id="user-456"
)

# Log request error
try:
    process_request()
except Exception as e:
    request_logger.log_error(
        method="POST",
        path="/api/users",
        error=e,
        request_id="req-abc-123"
    )
```

### Database Logging

```python
from logging_config import DatabaseLogger, get_logger

logger = get_logger(__name__)
db_logger = DatabaseLogger(logger)

# Log query
db_logger.log_query(
    query="SELECT * FROM users WHERE id = ?",
    params={"id": user_id},
    execution_time=0.05
)

# Log database error
try:
    execute_query()
except Exception as e:
    db_logger.log_error("query_execution", e)
```

### Integrating with FastAPI

```python
from fastapi import FastAPI, Request
from error_handlers import (
    APIError,
    api_error_handler,
    validation_exception_handler,
    general_exception_handler
)

app = FastAPI()

# Register error handlers
app.add_exception_handler(APIError, api_error_handler)
app.add_exception_handler(ValueError, validation_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    user = find_user(user_id)
    if not user:
        raise NotFoundError(f"User {user_id} not found")
    return user
```

## Error Response Format

All errors return a consistent JSON structure:

```json
{
  "error": {
    "message": "User not found",
    "status_code": 404,
    "code": "NOT_FOUND",
    "timestamp": "2024-03-03T10:30:00.000Z",
    "request_id": "req-abc-123",
    "details": {
      "user_id": 123
    }
  }
}
```

## Log Format

### JSON Format (Production)

```json
{
  "timestamp": "2024-03-03T10:30:00.000Z",
  "level": "INFO",
  "logger": "app.api",
  "message": "GET /api/users - 200 - 0.123s",
  "module": "api",
  "function": "get_users",
  "line": 45,
  "request_id": "req-abc-123",
  "status_code": 200,
  "process_time": "0.123s"
}
```

### Text Format (Development)

```
2024-03-03 10:30:00,000 - app.api - INFO - GET /api/users - 200 - 0.123s
```

## Testing

Comprehensive test coverage:

- `test_error_handlers.py`: 50+ tests for error classes and handlers
- `test_logging_config.py`: 30+ tests for logging configuration

Run tests:

```bash
cd backend
pytest test_error_handlers.py test_logging_config.py -v --cov
```

## Best Practices

1. **Use specific error classes** instead of generic exceptions
2. **Include details** in error objects for debugging
3. **Log at appropriate levels**:
   - DEBUG: Detailed diagnostic information
   - INFO: General informational messages
   - WARNING: Warning messages for potentially harmful situations
   - ERROR: Error messages for serious problems
   - CRITICAL: Critical messages for very serious errors

4. **Add request IDs** to track requests across logs
5. **Use structured logging** (JSON) in production
6. **Rotate log files** to prevent disk space issues
7. **Monitor error rates** and set up alerts
8. **Include context** in error messages

## Configuration

Environment variables:

```bash
# Logging
export LOG_LEVEL=INFO
export LOG_FILE=logs/app.log
export LOG_FORMAT=json  # or 'text'

# Error handling
export INCLUDE_ERROR_DETAILS=true  # Include stack traces in responses
export ERROR_NOTIFICATION_EMAIL=admin@example.com
```

## Monitoring and Alerts

### Key Metrics to Monitor

1. **Error rate**: Errors per minute/hour
2. **Error types**: Distribution of error codes
3. **Response times**: P50, P95, P99 percentiles
4. **Database errors**: Connection failures, query timeouts
5. **Rate limit hits**: Frequency of 429 errors

### Setting Up Alerts

- Alert on error rate > 5% of total requests
- Alert on critical errors (500s)
- Alert on database connection failures
- Alert on rate limit exceeded for specific IPs

## Future Enhancements

- [ ] Add error aggregation and reporting
- [ ] Implement error notification system (email/Slack)
- [ ] Add distributed tracing support
- [ ] Implement error recovery strategies
- [ ] Add performance monitoring integration
- [ ] Support for custom error handlers per endpoint

## Contributing

When adding new error types:

1. Create error class in `error_handlers.py`
2. Add appropriate status code and error code
3. Write tests in `test_error_handlers.py`
4. Update this documentation

## License

Part of the Smart Health project.
