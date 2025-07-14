"""Tests for agent utilities."""
import asyncio
import logging
import os
import time
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import pytest
from agent.utils import (
    setup_logging, get_logger, retry_async, retry_sync, 
    ErrorHandler, ConfigLoader, PerformanceTimer, 
    format_duration, sanitize_filename, ensure_directory
)


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create temporary config directory."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    return config_dir


@pytest.fixture
def temp_log_dir(tmp_path):
    """Create temporary log directory."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    return log_dir


class TestLogging:
    """Test suite for logging utilities."""
    
    def test_setup_logging_basic(self, temp_log_dir):
        """Test basic logging setup."""
        setup_logging(log_dir=str(temp_log_dir))
        
        logger = get_logger("test_logger")
        logger.info("Test message")
        
        # Check that log file was created
        log_files = list(temp_log_dir.glob("*.log"))
        assert len(log_files) > 0
    
    def test_setup_logging_with_level(self, temp_log_dir):
        """Test logging setup with specific level."""
        # Clear any existing logging configuration
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        setup_logging(log_dir=str(temp_log_dir), level=logging.WARNING)
        
        logger = get_logger("test_logger_unique")
        
        # Should have WARNING level (check root logger since that's what we set)
        assert root_logger.level == logging.WARNING
    
    def test_logger_rotation(self, temp_log_dir):
        """Test log file rotation."""
        setup_logging(
            log_dir=str(temp_log_dir),
            max_bytes=1024,  # Small size to trigger rotation
            backup_count=3
        )
        
        logger = get_logger("test_logger")
        
        # Write enough to trigger rotation
        for i in range(100):
            logger.info(f"Test message {i} " + "x" * 50)
        
        # Should have multiple log files
        log_files = list(temp_log_dir.glob("*.log*"))
        assert len(log_files) > 1
    
    def test_structured_logging(self, temp_log_dir):
        """Test structured logging with extra fields."""
        setup_logging(log_dir=str(temp_log_dir))
        
        logger = get_logger("test_logger")
        logger.info("Test message", extra={
            "task_id": "test-123",
            "confidence": 85.5,
            "action": "web_scrape"
        })
        
        # Check log file contains structured data
        log_file = next(temp_log_dir.glob("*.log"))
        content = log_file.read_text()
        assert "test-123" in content


class TestRetryDecorators:
    """Test suite for retry decorators."""
    
    @pytest.mark.asyncio
    async def test_retry_async_success(self):
        """Test async retry on eventual success."""
        call_count = 0
        
        @retry_async(max_attempts=3, delay=0.1)
        async def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"
        
        result = await flaky_function()
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_async_failure(self):
        """Test async retry with permanent failure."""
        @retry_async(max_attempts=2, delay=0.1)
        async def failing_function():
            raise ValueError("Permanent failure")
        
        with pytest.raises(ValueError, match="Permanent failure"):
            await failing_function()
    
    def test_retry_sync_success(self):
        """Test synchronous retry on eventual success."""
        call_count = 0
        
        @retry_sync(max_attempts=3, delay=0.1)
        def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Temporary failure")
            return "success"
        
        result = flaky_function()
        assert result == "success"
        assert call_count == 2
    
    def test_retry_sync_with_backoff(self):
        """Test retry with exponential backoff."""
        start_time = time.time()
        
        @retry_sync(max_attempts=3, delay=0.1, backoff_multiplier=2.0)
        def failing_function():
            raise Exception("Always fails")
        
        with pytest.raises(Exception):
            failing_function()
        
        # Should take at least 0.1 + 0.2 = 0.3 seconds due to backoff
        elapsed = time.time() - start_time
        assert elapsed >= 0.3
    
    @pytest.mark.asyncio
    async def test_retry_specific_exceptions(self):
        """Test retry only on specific exception types."""
        @retry_async(max_attempts=3, delay=0.1, exceptions=(ValueError,))
        async def selective_retry():
            raise TypeError("Wrong exception type")
        
        # Should not retry TypeError
        with pytest.raises(TypeError):
            await selective_retry()


class TestErrorHandler:
    """Test suite for error handling utilities."""
    
    def test_error_handler_initialization(self):
        """Test error handler initialization."""
        handler = ErrorHandler(logger_name="test")
        
        assert handler.logger is not None
        assert handler.error_count == 0
        assert len(handler.error_history) == 0
    
    def test_handle_error_logging(self):
        """Test error handling and logging."""
        handler = ErrorHandler(logger_name="test")
        
        try:
            raise ValueError("Test error")
        except ValueError as e:
            handler.handle_error(e, context={"task_id": "test-123"})
        
        assert handler.error_count == 1
        assert len(handler.error_history) == 1
        assert handler.error_history[0]["exception_type"] == "ValueError"
    
    def test_error_recovery_suggestions(self):
        """Test error recovery suggestions."""
        handler = ErrorHandler(logger_name="test")
        
        # ConnectionError should suggest network-related recovery
        try:
            raise ConnectionError("Network unavailable")
        except ConnectionError as e:
            suggestions = handler.get_recovery_suggestions(e)
            assert any("network" in s.lower() for s in suggestions)
        
        # FileNotFoundError should suggest file-related recovery
        try:
            raise FileNotFoundError("File missing")
        except FileNotFoundError as e:
            suggestions = handler.get_recovery_suggestions(e)
            assert any("file" in s.lower() or "path" in s.lower() for s in suggestions)
    
    def test_error_rate_tracking(self):
        """Test error rate calculation."""
        handler = ErrorHandler(logger_name="test")
        
        # Simulate errors over time
        for i in range(5):
            try:
                raise Exception(f"Error {i}")
            except Exception as e:
                handler.handle_error(e)
        
        # Error rate should be calculable
        rate = handler.get_error_rate(window_minutes=60)
        assert rate >= 0
    
    def test_critical_error_detection(self):
        """Test critical error detection."""
        handler = ErrorHandler(logger_name="test")
        
        # Regular error
        try:
            raise ValueError("Regular error")
        except ValueError as e:
            is_critical = handler.is_critical_error(e)
            assert not is_critical
        
        # Critical error (memory, system, etc.)
        try:
            raise MemoryError("Out of memory")
        except MemoryError as e:
            is_critical = handler.is_critical_error(e)
            assert is_critical


class TestConfigLoader:
    """Test suite for configuration loading."""
    
    def test_load_yaml_config(self, temp_config_dir):
        """Test loading YAML configuration."""
        config_file = temp_config_dir / "test.yaml"
        config_file.write_text("""
api_key: test-key
timeout: 30
debug: true
urls:
  - https://example.com
  - https://test.com
""")
        
        loader = ConfigLoader(str(temp_config_dir))
        config = loader.load_config("test.yaml")
        
        assert config["api_key"] == "test-key"
        assert config["timeout"] == 30
        assert config["debug"] is True
        assert len(config["urls"]) == 2
    
    def test_load_json_config(self, temp_config_dir):
        """Test loading JSON configuration."""
        config_file = temp_config_dir / "test.json"
        config_file.write_text('{"api_key": "test-key", "timeout": 30}')
        
        loader = ConfigLoader(str(temp_config_dir))
        config = loader.load_config("test.json")
        
        assert config["api_key"] == "test-key"
        assert config["timeout"] == 30
    
    def test_config_with_env_variables(self, temp_config_dir):
        """Test configuration with environment variable substitution."""
        config_file = temp_config_dir / "test.yaml"
        config_file.write_text("""
api_key: ${API_KEY}
timeout: ${TIMEOUT:45}
""")
        
        with patch.dict(os.environ, {"API_KEY": "env-key"}):
            loader = ConfigLoader(str(temp_config_dir))
            config = loader.load_config("test.yaml")
            
            assert config["api_key"] == "env-key"
            assert config["timeout"] == 45  # Default value
    
    def test_config_validation(self, temp_config_dir):
        """Test configuration validation."""
        config_file = temp_config_dir / "test.yaml"
        config_file.write_text("""
api_key: test-key
timeout: 30
""")
        
        schema = {
            "type": "object",
            "properties": {
                "api_key": {"type": "string"},
                "timeout": {"type": "number", "minimum": 0}
            },
            "required": ["api_key"]
        }
        
        loader = ConfigLoader(str(temp_config_dir))
        config = loader.load_config("test.yaml", schema=schema)
        
        assert config is not None  # Should validate successfully
    
    def test_missing_config_file(self, temp_config_dir):
        """Test handling of missing configuration file."""
        loader = ConfigLoader(str(temp_config_dir))
        
        with pytest.raises(FileNotFoundError):
            loader.load_config("nonexistent.yaml")


class TestPerformanceTimer:
    """Test suite for performance timing utilities."""
    
    def test_performance_timer_context(self):
        """Test performance timer as context manager."""
        with PerformanceTimer() as timer:
            time.sleep(0.1)
        
        assert timer.elapsed >= 0.1
        assert timer.elapsed < 0.2  # Should be close to 0.1
    
    def test_performance_timer_decorator(self):
        """Test performance timer as decorator."""
        @PerformanceTimer.time_function
        def slow_function():
            time.sleep(0.1)
            return "result"
        
        result = slow_function()
        assert result == "result"
        # Timer info should be logged (would need to check logs in real implementation)
    
    def test_performance_timer_manual(self):
        """Test manual performance timing."""
        timer = PerformanceTimer()
        timer.start()
        time.sleep(0.1)
        elapsed = timer.stop()
        
        assert elapsed >= 0.1
        assert timer.elapsed == elapsed
    
    def test_performance_timer_multiple_measurements(self):
        """Test multiple timing measurements."""
        timer = PerformanceTimer()
        
        # First measurement
        timer.start()
        time.sleep(0.05)
        time1 = timer.stop()
        
        # Second measurement
        timer.start()
        time.sleep(0.1)
        time2 = timer.stop()
        
        assert time2 > time1


class TestUtilityFunctions:
    """Test suite for utility functions."""
    
    def test_format_duration(self):
        """Test duration formatting."""
        assert format_duration(30) == "30.0s"
        assert format_duration(90) == "1m 30s"
        assert format_duration(3661) == "1h 1m 1s"
        assert format_duration(0.5) == "0.5s"
    
    def test_sanitize_filename(self):
        """Test filename sanitization."""
        assert sanitize_filename("normal_file.txt") == "normal_file.txt"
        assert sanitize_filename("file with spaces.txt") == "file_with_spaces.txt"
        assert sanitize_filename("file/with\\slashes.txt") == "file_with_slashes.txt"
        assert sanitize_filename("file:with*special?chars.txt") == "file_with_special_chars.txt"
    
    def test_ensure_directory(self, tmp_path):
        """Test directory creation utility."""
        test_dir = tmp_path / "nested" / "directory" / "structure"
        
        ensure_directory(test_dir)
        
        assert test_dir.exists()
        assert test_dir.is_dir()
        
        # Should not raise error if already exists
        ensure_directory(test_dir)
    
    def test_ensure_directory_with_file_path(self, tmp_path):
        """Test directory creation from file path."""
        file_path = tmp_path / "nested" / "directory" / "file.txt"
        
        ensure_directory(file_path, is_file_path=True)
        
        assert file_path.parent.exists()
        assert file_path.parent.is_dir()
        assert not file_path.exists()  # File itself should not be created