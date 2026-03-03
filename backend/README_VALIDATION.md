# Validation System Documentation

## Overview

This comprehensive validation system provides robust input validation, security middleware, and configuration management for the Smart Health API.

## Components

### 1. Validators (`validators.py`)

Input validation functions for various data types:

- **Symptom Validation**: Validates user-submitted symptom descriptions
  - Length constraints (3-500 characters)
  - XSS protection
  - Injection attack prevention

- **Email Validation**: RFC-compliant email format validation
  - Format checking with regex
  - Length validation (max 254 characters)

- **Phone Number Validation**: International phone number validation
  - Digit-only validation after formatting removal
  - Length constraints (10-15 digits)
  - Supports common formatting: `+1 (234) 567-8900`

- **Appointment Date Validation**: Future date validation
  - Must be in the future
  - Cannot be more than 365 days ahead
  - ISO format (YYYY-MM-DD)

- **User Data Validation**: Complete user registration validation
  - Name, email, and optional phone validation
  - Returns detailed error dictionary

### 2. Configuration (`config.py`)

Centralized configuration management:

- **ValidationConfig**: Validation rules and constraints
- **APIConfig**: API settings, CORS, rate limiting
- **DatabaseConfig**: Database connection settings
- **SecurityConfig**: JWT, password, and session settings

### 3. Middleware (`middleware.py`)

Request processing middleware:

- **RequestValidationMiddleware**: 
  - Validates content types
  - Logs requests and responses
  - Adds process time headers

- **SecurityHeadersMiddleware**:
  - Adds security headers (HSTS, CSP, X-Frame-Options)
  - Prevents clickjacking and XSS
  - Enforces HTTPS

- **RateLimitMiddleware**:
  - Simple rate limiting (60 requests/minute default)
  - Per-IP tracking
  - Automatic cleanup of old entries

## Usage Examples

### Validating Symptom Input

```python
from validators import validate_symptom_input

is_valid, error = validate_symptom_input("I have a headache")
if not is_valid:
    return {"error": error}
```

### Validating User Registration

```python
from validators import validate_user_data

user_data = {
    "name": "John Doe",
    "email": "john@example.com",
    "phone": "+1 234 567 8900"
}

is_valid, errors = validate_user_data(user_data)
if not is_valid:
    return {"errors": errors}
```

### Adding Middleware to FastAPI

```python
from fastapi import FastAPI
from middleware import (
    RequestValidationMiddleware,
    SecurityHeadersMiddleware,
    RateLimitMiddleware
)

app = FastAPI()

# Add middleware (order matters!)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestValidationMiddleware)
app.add_middleware(RateLimitMiddleware, max_requests=60, window_seconds=60)
```

### Using Configuration

```python
from config import validation_config, api_config

# Access validation settings
max_length = validation_config.MAX_SYMPTOM_LENGTH

# Access API settings
cors_origins = api_config.CORS_ORIGINS
```

## Testing

All components have comprehensive unit tests:

- `test_validators.py`: 40+ test cases for all validators
- `test_middleware.py`: 20+ test cases for middleware

Run tests with pytest:

```bash
cd backend
pytest test_validators.py test_middleware.py -v
```

## Security Features

1. **XSS Protection**: Blocks script tags and JavaScript injection
2. **SQL Injection Protection**: Input sanitization (configurable)
3. **Rate Limiting**: Prevents abuse and DDoS attacks
4. **Security Headers**: HSTS, CSP, X-Frame-Options, etc.
5. **Content Type Validation**: Ensures proper JSON requests

## Configuration

Environment variables can override default settings:

```bash
# API Configuration
export CORS_ORIGINS="http://localhost:3000,https://example.com"
export RATE_LIMIT_PER_MINUTE=100
export LOG_LEVEL=DEBUG

# Database Configuration
export DATABASE_URL="postgresql://user:pass@localhost/db"
export DB_POOL_SIZE=10

# Security Configuration
export SECRET_KEY="your-secret-key"
export ACCESS_TOKEN_EXPIRE_MINUTES=60
```

## Best Practices

1. **Always validate user input** before processing
2. **Use middleware** for cross-cutting concerns
3. **Configure rate limits** based on your needs
4. **Enable all security headers** in production
5. **Log validation failures** for monitoring
6. **Test edge cases** thoroughly

## Future Enhancements

- [ ] Add password strength validation
- [ ] Implement CAPTCHA for rate-limited endpoints
- [ ] Add request signature validation
- [ ] Support custom validation rules via config
- [ ] Add validation for file uploads
- [ ] Implement IP whitelist/blacklist

## Contributing

When adding new validators:

1. Add the validator function to `validators.py`
2. Add configuration to `config.py` if needed
3. Write comprehensive tests in `test_validators.py`
4. Update this documentation

## License

Part of the Smart Health project.
