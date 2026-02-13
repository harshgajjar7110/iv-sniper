"""
Error Handling Utilities Module

Provides standardized error handling patterns for the IV-Sniper application:
- Custom exception classes
- Error logging decorators
- Error context managers
- Standardized error formatting

Usage:
    from ui.utils.error_handlers import (
        IVSniperError,
        handle_database_error,
        handle_api_error,
        with_error_handling,
    )
"""

import functools
import logging
import traceback
from typing import Any, Callable, Optional, Type, TypeVar, Union

logger = logging.getLogger(__name__)

# Type variable for generic function return type
T = TypeVar('T')


# =============================================================================
# Custom Exception Classes
# =============================================================================

class IVSniperError(Exception):
    """Base exception class for IV-Sniper application."""
    
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
    
    def __str__(self) -> str:
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.message} ({details_str})"
        return self.message


class DatabaseError(IVSniperError):
    """Exception raised for database-related errors."""
    pass


class APIError(IVSniperError):
    """Exception raised for API-related errors."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, 
                 details: Optional[dict] = None):
        super().__init__(message, details)
        self.status_code = status_code


class ValidationError(IVSniperError):
    """Exception raised for validation errors."""
    pass


class ConfigurationError(IVSniperError):
    """Exception raised for configuration-related errors."""
    pass


class OrderError(IVSniperError):
    """Exception raised for order execution errors."""
    pass


class DataError(IVSniperError):
    """Exception raised for data processing errors."""
    pass


# =============================================================================
# Error Logging Functions
# =============================================================================

def log_error(
    logger_instance: logging.Logger,
    level: str = "error",
    context: Optional[str] = None,
    exc_info: Optional[Exception] = None,
    **kwargs
) -> None:
    """
    Standardized error logging with context.
    
    Args:
        logger_instance: Logger instance to use
        level: Log level ('debug', 'info', 'warning', 'error', 'critical')
        context: Context description for the error
        exc_info: Exception object if available
        **kwargs: Additional key-value pairs to log
    """
    log_func = getattr(logger_instance, level.lower(), logger_instance.error)
    
    message_parts = []
    if context:
        message_parts.append(f"[{context}]")
    
    if exc_info:
        message_parts.append(str(exc_info))
    
    if kwargs:
        details = ", ".join(f"{k}={v}" for k, v in kwargs.items())
        message_parts.append(details)
    
    message = " ".join(message_parts) if message_parts else "An error occurred"
    
    if exc_info and level.lower() in ('error', 'critical'):
        # Include stack trace for errors
        log_func(message, exc_info=True)
    else:
        log_func(message)


def log_database_error(
    logger_instance: logging.Logger,
    operation: str,
    error: Exception,
    query: Optional[str] = None,
    **kwargs
) -> None:
    """
    Log database errors with standardized format.
    
    Args:
        logger_instance: Logger instance
        operation: Database operation (e.g., 'SELECT', 'INSERT', 'UPDATE')
        error: The exception that occurred
        query: SQL query that caused the error (optional)
        **kwargs: Additional context
    """
    logger_instance.error(
        f"Database error during {operation}: {error}",
        extra={
            "operation": operation,
            "query": query[:200] if query else None,  # Truncate long queries
            "error_type": type(error).__name__,
            **kwargs
        }
    )


def log_api_error(
    logger_instance: logging.Logger,
    api_name: str,
    error: Exception,
    status_code: Optional[int] = None,
    response_data: Optional[dict] = None,
    **kwargs
) -> None:
    """
    Log API errors with standardized format.
    
    Args:
        logger_instance: Logger instance
        api_name: Name of the API endpoint
        error: The exception that occurred
        status_code: HTTP status code if available
        response_data: API response data if available
        **kwargs: Additional context
    """
    logger_instance.error(
        f"API error in {api_name}: {error}",
        extra={
            "api_name": api_name,
            "status_code": status_code,
            "response_data": str(response_data)[:200] if response_data else None,
            "error_type": type(error).__name__,
            **kwargs
        }
    )


# =============================================================================
# Error Handling Decorators
# =============================================================================

def with_error_handling(
    error_message: str = "An error occurred",
    default_return: Any = None,
    reraise: bool = False,
    exceptions: tuple = (Exception,)
) -> Callable:
    """
    Decorator to add standardized error handling to functions.
    
    Args:
        error_message: Custom error message to log
        default_return: Value to return on error
        reraise: Whether to re-raise the exception after logging
        exceptions: Tuple of exception types to catch
    
    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., Optional[T]]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Optional[T]:
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                logger.error(f"{error_message}: {e}", exc_info=True)
                if reraise:
                    raise
                return default_return
        return wrapper
    return decorator


def handle_database_errors(
    operation: str = "database operation",
    default_return: Any = None,
    reraise: bool = False
) -> Callable:
    """
    Decorator specifically for database error handling.
    
    Args:
        operation: Description of the database operation
        default_return: Value to return on error
        reraise: Whether to re-raise the exception after logging
    
    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., Optional[T]]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Optional[T]:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                log_database_error(logger, operation, e)
                if reraise:
                    raise DatabaseError(f"Failed to {operation}: {e}") from e
                return default_return
        return wrapper
    return decorator


def handle_api_errors(
    api_name: str = "API",
    default_return: Any = None,
    reraise: bool = False
) -> Callable:
    """
    Decorator specifically for API error handling.
    
    Args:
        api_name: Name of the API
        default_return: Value to return on error
        reraise: Whether to re-raise the exception after logging
    
    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., Optional[T]]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Optional[T]:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                log_api_error(logger, api_name, e)
                if reraise:
                    raise APIError(f"API {api_name} failed: {e}") from e
                return default_return
        return wrapper
    return decorator


# =============================================================================
# Error Context Managers
# =============================================================================

class ErrorContext:
    """
    Context manager for standardized error handling.
    
    Usage:
        with ErrorContext("fetching quotes", logger):
            quotes = kite.ltp(symbols)
    """
    
    def __init__(
        self, 
        context: str, 
        logger_instance: logging.Logger,
        reraise: bool = False,
        default_return: Any = None
    ):
        self.context = context
        self.logger = logger_instance
        self.reraise = reraise
        self.default_return = default_return
        self.error: Optional[Exception] = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.error = exc_val
            self.logger.error(
                f"Error during {self.context}: {exc_val}",
                exc_info=True
            )
            if self.reraise:
                return False  # Re-raise the exception
            return True  # Suppress the exception


class DatabaseErrorContext(ErrorContext):
    """Context manager specifically for database operations."""
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.error = exc_val
            log_database_error(self.logger, self.context, exc_val)
            if self.reraise:
                return False
            return True
        return True


class APIErrorContext(ErrorContext):
    """Context manager specifically for API operations."""
    
    def __init__(
        self, 
        context: str, 
        logger_instance: logging.Logger,
        reraise: bool = False,
        default_return: Any = None,
        status_code: Optional[int] = None
    ):
        super().__init__(context, logger_instance, reraise, default_return)
        self.status_code = status_code
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.error = exc_val
            log_api_error(self.logger, self.context, exc_val, self.status_code)
            if self.reraise:
                return False
            return True
        return True


# =============================================================================
# Error Formatting
# =============================================================================

def format_error_message(
    error: Exception,
    include_type: bool = True,
    include_traceback: bool = False
) -> str:
    """
    Format an exception into a user-friendly error message.
    
    Args:
        error: Exception to format
        include_type: Whether to include exception type
        include_traceback: Whether to include stack trace
    
    Returns:
        Formatted error message
    """
    parts = []
    
    if include_type:
        parts.append(f"[{type(error).__name__}]")
    
    parts.append(str(error))
    
    message = " ".join(parts)
    
    if include_traceback:
        message += "\n" + traceback.format_exc()
    
    return message


def get_user_friendly_message(error: Exception) -> str:
    """
    Convert technical exceptions to user-friendly messages.
    
    Args:
        error: Exception to convert
    
    Returns:
        User-friendly message
    """
    error_type = type(error).__name__
    error_message = str(error)
    
    # Map technical errors to user-friendly messages
    error_mapping = {
        'ConnectionError': "Unable to connect to the server. Please check your internet connection.",
        'TimeoutError': "The request timed out. Please try again.",
        'KeyError': "Required data is missing. Please refresh and try again.",
        'ValueError': 'Invalid value provided. Please check your input.',
        'DatabaseError': "A database error occurred. Please try again later.",
        'APIError': "An external API error occurred. Please try again.",
    }
    
    # Check for specific error patterns
    if "authentication" in error_message.lower() or "unauthorized" in error_message.lower():
        return "Authentication failed. Please log in again."
    
    if "timeout" in error_message.lower():
        return "The request timed out. Please try again."
    
    if "connection" in error_message.lower():
        return "Unable to connect. Please check your internet connection."
    
    # Return mapped message or generic fallback
    return error_mapping.get(error_type, f"An error occurred: {error_message[:100]}")


# =============================================================================
# Safe Execution Utilities
# =============================================================================

def safe_execute(
    func: Callable[..., T],
    *args,
    default: Any = None,
    error_message: str = "Execution failed",
    **kwargs
) -> T:
    """
    Safely execute a function with error handling.
    
    Args:
        func: Function to execute
        *args: Positional arguments
        default: Default value to return on error
        error_message: Error message to log
        **kwargs: Keyword arguments
    
    Returns:
        Function result or default value
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(f"{error_message}: {e}", exc_info=True)
        return default


def safe_get(data: dict, *keys: str, default: Any = None) -> Any:
    """
    Safely get nested dictionary values.
    
    Args:
        data: Dictionary to get value from
        *keys: Nested keys to traverse
        default: Default value if key not found
    
    Returns:
        Value at keys or default
    """
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
            if current is None:
                return default
        else:
            return default
    return current if current is not None else default


def safe_convert(
    value: Any,
    target_type: Type,
    default: Any = None
) -> Any:
    """
    Safely convert a value to target type.
    
    Args:
        value: Value to convert
        target_type: Target type (int, float, str, etc.)
        default: Default value on conversion failure
    
    Returns:
        Converted value or default
    """
    if value is None:
        return default
    
    try:
        return target_type(value)
    except (ValueError, TypeError):
        return default
