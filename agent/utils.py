"""Utility functions for logging, error handling, and retry logic."""
import asyncio
import functools
import json
import logging
import logging.handlers
import os
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Type, Union
import yaml


def setup_logging(
    log_dir: str = "logs",
    level: int = logging.INFO,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    format_string: Optional[str] = None
):
    """Set up structured logging with rotation."""
    # Create log directory
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # File handler with rotation
    log_file = log_path / "agent.log"
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    file_handler.setLevel(level)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    
    # Custom formatter that includes extra fields
    class StructuredFormatter(logging.Formatter):
        def format(self, record):
            # Default format
            if format_string is None:
                base_format = (
                    "%(asctime)s | %(name)s | %(levelname)s | %(message)s | "
                    "%(pathname)s:%(lineno)d"
                )
            else:
                base_format = format_string
            
            # Format base message
            formatter = logging.Formatter(base_format)
            message = formatter.format(record)
            
            # Add extra fields if present
            extra_fields = []
            for key, value in record.__dict__.items():
                if key not in {'name', 'msg', 'args', 'levelname', 'levelno', 
                              'pathname', 'filename', 'module', 'lineno', 'funcName',
                              'created', 'msecs', 'relativeCreated', 'thread',
                              'threadName', 'processName', 'process', 'message',
                              'exc_info', 'exc_text', 'stack_info', 'asctime'}:
                    extra_fields.append(f"{key}={value}")
            
            if extra_fields:
                message += " | " + " | ".join(extra_fields)
            
            return message
    
    formatter = StructuredFormatter()
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Add handlers
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    logger = logging.getLogger(name)
    # Inherit level from root logger if not explicitly set
    if logger.level == logging.NOTSET:
        logger.setLevel(logging.getLogger().level)
    return logger


def retry_async(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff_multiplier: float = 1.5,
    exceptions: tuple = (Exception,)
):
    """Decorator for async functions with retry logic."""
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_attempts - 1:  # Don't delay after last attempt
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff_multiplier
                    
                    # Log retry attempt
                    logger = get_logger(func.__module__)
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_attempts} failed for {func.__name__}: {e}",
                        extra={"attempt": attempt + 1, "max_attempts": max_attempts}
                    )
            
            # All attempts failed
            logger = get_logger(func.__module__)
            logger.error(f"All {max_attempts} attempts failed for {func.__name__}")
            raise last_exception
        
        return wrapper
    return decorator


def retry_sync(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff_multiplier: float = 1.5,
    exceptions: tuple = (Exception,)
):
    """Decorator for synchronous functions with retry logic."""
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_attempts - 1:  # Don't delay after last attempt
                        time.sleep(current_delay)
                        current_delay *= backoff_multiplier
                    
                    # Log retry attempt
                    logger = get_logger(func.__module__)
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_attempts} failed for {func.__name__}: {e}",
                        extra={"attempt": attempt + 1, "max_attempts": max_attempts}
                    )
            
            # All attempts failed
            logger = get_logger(func.__module__)
            logger.error(f"All {max_attempts} attempts failed for {func.__name__}")
            raise last_exception
        
        return wrapper
    return decorator


class ErrorHandler:
    """Centralized error handling and recovery suggestions."""
    
    def __init__(self, logger_name: str = __name__):
        """Initialize error handler."""
        self.logger = get_logger(logger_name)
        self.error_count = 0
        self.error_history: List[Dict[str, Any]] = []
        self.critical_errors = {
            MemoryError, SystemError, OSError, KeyboardInterrupt
        }
    
    def handle_error(
        self, 
        exception: Exception, 
        context: Optional[Dict[str, Any]] = None,
        reraise: bool = False
    ):
        """Handle an error with logging and tracking."""
        self.error_count += 1
        
        error_info = {
            "timestamp": datetime.now().isoformat(),
            "exception_type": type(exception).__name__,
            "message": str(exception),
            "context": context or {},
            "is_critical": self.is_critical_error(exception)
        }
        
        self.error_history.append(error_info)
        
        # Log with appropriate level
        if error_info["is_critical"]:
            self.logger.critical(
                f"Critical error: {exception}",
                extra={"error_info": error_info}
            )
        else:
            self.logger.error(
                f"Error: {exception}",
                extra={"error_info": error_info}
            )
        
        # Limit history size
        if len(self.error_history) > 100:
            self.error_history = self.error_history[-100:]
        
        if reraise:
            raise exception
    
    def is_critical_error(self, exception: Exception) -> bool:
        """Determine if an error is critical."""
        return type(exception) in self.critical_errors
    
    def get_recovery_suggestions(self, exception: Exception) -> List[str]:
        """Get recovery suggestions for specific error types."""
        suggestions = []
        error_type = type(exception)
        error_msg = str(exception).lower()
        
        if error_type == ConnectionError or "connection" in error_msg:
            suggestions.extend([
                "Check network connectivity",
                "Verify server endpoints are accessible",
                "Consider increasing timeout values",
                "Implement connection pooling"
            ])
        
        elif error_type == FileNotFoundError or "no such file" in error_msg:
            suggestions.extend([
                "Verify file paths are correct",
                "Check file permissions",
                "Ensure required directories exist",
                "Consider using absolute paths"
            ])
        
        elif error_type == MemoryError or "memory" in error_msg:
            suggestions.extend([
                "Reduce batch sizes",
                "Implement data streaming",
                "Clear unnecessary variables",
                "Consider processing in chunks"
            ])
        
        elif error_type == TimeoutError or "timeout" in error_msg:
            suggestions.extend([
                "Increase timeout values",
                "Optimize query/request performance",
                "Implement retry with backoff",
                "Consider async processing"
            ])
        
        elif "rate limit" in error_msg or "429" in error_msg:
            suggestions.extend([
                "Implement rate limiting",
                "Add delays between requests",
                "Use exponential backoff",
                "Consider request batching"
            ])
        
        else:
            suggestions.extend([
                "Review error context and logs",
                "Check input data validity",
                "Verify configuration settings",
                "Consider error-specific handling"
            ])
        
        return suggestions
    
    def get_error_rate(self, window_minutes: int = 60) -> float:
        """Calculate error rate within time window."""
        if not self.error_history:
            return 0.0
        
        cutoff_time = datetime.now() - timedelta(minutes=window_minutes)
        recent_errors = [
            e for e in self.error_history
            if datetime.fromisoformat(e["timestamp"]) > cutoff_time
        ]
        
        return len(recent_errors) / window_minutes  # Errors per minute
    
    def reset_error_tracking(self):
        """Reset error tracking counters."""
        self.error_count = 0
        self.error_history = []


class ConfigLoader:
    """Configuration loading and validation utilities."""
    
    def __init__(self, config_dir: str = "config"):
        """Initialize config loader."""
        self.config_dir = Path(config_dir)
        self.logger = get_logger(self.__class__.__name__)
    
    def load_config(
        self, 
        filename: str, 
        schema: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Load configuration from YAML or JSON file."""
        config_path = self.config_dir / filename
        
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        # Load based on file extension
        try:
            if filename.endswith(('.yaml', '.yml')):
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
            elif filename.endswith('.json'):
                with open(config_path, 'r') as f:
                    config = json.load(f)
            else:
                raise ValueError(f"Unsupported config format: {filename}")
        
        except Exception as e:
            self.logger.error(f"Failed to load config {filename}: {e}")
            raise
        
        # Environment variable substitution
        config = self._substitute_env_vars(config)
        
        # Schema validation (simplified - would use jsonschema in production)
        if schema:
            self._validate_config(config, schema)
        
        self.logger.info(f"Loaded configuration from {filename}")
        return config
    
    def _substitute_env_vars(self, config: Any) -> Any:
        """Substitute environment variables in config values."""
        if isinstance(config, dict):
            return {k: self._substitute_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._substitute_env_vars(item) for item in config]
        elif isinstance(config, str):
            # Look for ${VAR} or ${VAR:default} patterns
            pattern = r'\$\{([^}:]+)(?::([^}]*))?\}'
            
            def replacer(match):
                var_name = match.group(1)
                default_value = match.group(2)
                value = os.getenv(var_name, default_value)
                
                # Return as string for regex substitution
                return str(value) if value is not None else ""
            
            result = re.sub(pattern, replacer, config)
            
            # Try to convert result to appropriate type
            if result.isdigit():
                return int(result)
            elif result.replace('.', '', 1).isdigit():
                return float(result)
            elif result.lower() in ('true', 'false'):
                return result.lower() == 'true'
            
            return result
        else:
            return config
    
    def _validate_config(self, config: Dict, schema: Dict):
        """Basic config validation (simplified)."""
        # In production, would use jsonschema library
        required = schema.get("required", [])
        for field in required:
            if field not in config:
                raise ValueError(f"Required config field missing: {field}")


class PerformanceTimer:
    """Performance timing utilities."""
    
    def __init__(self):
        """Initialize performance timer."""
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.elapsed: float = 0.0
        self.logger = get_logger(self.__class__.__name__)
    
    def start(self):
        """Start timing."""
        self.start_time = time.time()
        self.end_time = None
    
    def stop(self) -> float:
        """Stop timing and return elapsed time."""
        if self.start_time is None:
            raise ValueError("Timer not started")
        
        self.end_time = time.time()
        self.elapsed = self.end_time - self.start_time
        return self.elapsed
    
    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
    
    @classmethod
    def time_function(cls, func: Callable):
        """Decorator to time function execution."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            timer = cls()
            timer.start()
            try:
                result = func(*args, **kwargs)
                elapsed = timer.stop()
                timer.logger.info(
                    f"Function {func.__name__} completed in {format_duration(elapsed)}",
                    extra={"function": func.__name__, "elapsed": elapsed}
                )
                return result
            except Exception as e:
                elapsed = timer.stop()
                timer.logger.error(
                    f"Function {func.__name__} failed after {format_duration(elapsed)}: {e}",
                    extra={"function": func.__name__, "elapsed": elapsed, "error": str(e)}
                )
                raise
        
        return wrapper


def format_duration(seconds: float) -> str:
    """Format duration in seconds to human-readable string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    
    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)
    
    if minutes < 60:
        return f"{minutes}m {remaining_seconds}s"
    
    hours = int(minutes // 60)
    remaining_minutes = int(minutes % 60)
    
    return f"{hours}h {remaining_minutes}m {remaining_seconds}s"


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe filesystem storage."""
    # Replace problematic characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Replace spaces with underscores
    sanitized = re.sub(r'\s+', '_', sanitized)
    
    # Remove or replace other special characters
    sanitized = re.sub(r'[^\w\-_.]', '_', sanitized)
    
    # Remove multiple consecutive underscores
    sanitized = re.sub(r'_+', '_', sanitized)
    
    # Remove leading/trailing underscores
    sanitized = sanitized.strip('_')
    
    return sanitized


def ensure_directory(path: Union[str, Path], is_file_path: bool = False):
    """Ensure directory exists, creating it if necessary."""
    path = Path(path)
    
    if is_file_path:
        # Create parent directory for file path
        directory = path.parent
    else:
        # Path itself is the directory
        directory = path
    
    directory.mkdir(parents=True, exist_ok=True)


def retry_with_backoff(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    backoff_multiplier: float = 2.0,
    exceptions: tuple = (Exception,),
    jitter: bool = True
):
    """
    Decorator for functions with exponential backoff retry logic.
    
    Args:
        max_attempts: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        backoff_multiplier: Multiplier for exponential backoff
        exceptions: Tuple of exception types to catch and retry on
        jitter: Add random jitter to delay to prevent thundering herd
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import random
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_attempts - 1:  # Don't delay after last attempt
                        # Calculate delay with exponential backoff
                        delay = initial_delay * (backoff_multiplier ** attempt)
                        
                        # Add jitter to prevent thundering herd
                        if jitter:
                            delay += random.uniform(0, delay * 0.1)
                        
                        time.sleep(delay)
                    
                    # Log retry attempt
                    logger = get_logger(func.__module__)
                    logger.warning(
                        f"Retry {attempt + 1}/{max_attempts} for {func.__name__}: {e}",
                        extra={
                            "attempt": attempt + 1, 
                            "max_attempts": max_attempts,
                            "delay": delay if attempt < max_attempts - 1 else 0,
                            "function": func.__name__,
                            "exception": str(e)
                        }
                    )
            
            # All attempts failed
            logger = get_logger(func.__module__)
            logger.error(
                f"All {max_attempts} attempts failed for {func.__name__}: {last_exception}",
                extra={
                    "function": func.__name__,
                    "max_attempts": max_attempts,
                    "final_exception": str(last_exception)
                }
            )
            raise last_exception
        
        return wrapper
    return decorator


async def retry_with_backoff_async(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    backoff_multiplier: float = 2.0,
    exceptions: tuple = (Exception,),
    jitter: bool = True
):
    """
    Async decorator for functions with exponential backoff retry logic.
    
    Args:
        max_attempts: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        backoff_multiplier: Multiplier for exponential backoff
        exceptions: Tuple of exception types to catch and retry on
        jitter: Add random jitter to delay to prevent thundering herd
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            import random
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_attempts - 1:  # Don't delay after last attempt
                        # Calculate delay with exponential backoff
                        delay = initial_delay * (backoff_multiplier ** attempt)
                        
                        # Add jitter to prevent thundering herd
                        if jitter:
                            delay += random.uniform(0, delay * 0.1)
                        
                        await asyncio.sleep(delay)
                    
                    # Log retry attempt
                    logger = get_logger(func.__module__)
                    logger.warning(
                        f"Async retry {attempt + 1}/{max_attempts} for {func.__name__}: {e}",
                        extra={
                            "attempt": attempt + 1, 
                            "max_attempts": max_attempts,
                            "delay": delay if attempt < max_attempts - 1 else 0,
                            "function": func.__name__,
                            "exception": str(e)
                        }
                    )
            
            # All attempts failed
            logger = get_logger(func.__module__)
            logger.error(
                f"All {max_attempts} async attempts failed for {func.__name__}: {last_exception}",
                extra={
                    "function": func.__name__,
                    "max_attempts": max_attempts,
                    "final_exception": str(last_exception)
                }
            )
            raise last_exception
        
        return wrapper
    return decorator