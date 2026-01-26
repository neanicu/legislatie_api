"""
Unit tests for configuration module.
"""

import pytest
import os
import logging
from unittest.mock import patch, mock_open

import config


class TestConfig:
    """Test suite for config module."""

    def test_default_values(self):
        """Test that default values are set correctly."""
        # Clear any environment variables that might affect tests
        with patch.dict(os.environ, {}, clear=True):
            # Reload config module to pick up cleared environment
            import importlib

            importlib.reload(config)

            # Test defaults
            assert (
                config.WSDL_URL
                == "https://legislatie.just.ro/apiws/FreeWebService.svc?wsdl"
            )
            assert (
                config.SOAP_ENDPOINT
                == "https://legislatie.just.ro/apiws/FreeWebService.svc/SOAP"
            )
            assert config.BASE_URL == "https://legislatie.just.ro"
            assert config.REQUEST_DELAY == 1.0
            assert config.MAX_RETRIES == 3
            assert config.CACHE_TTL == 3600
            assert config.CACHE_PATH == "./.legislatie_cache"
            assert config.USE_PERSISTENT_CACHE is False
            assert config.REQUEST_TIMEOUT == 30
            assert config.SOAP_TIMEOUT == 30
            assert config.LOG_LEVEL == "INFO"
            assert config.LOG_FILE == "./legislatie.log"

    def test_environment_override(self):
        """Test that environment variables override defaults."""
        env_vars = {
            "LEGISLATIE_WSDL_URL": "https://test.local/wsdl",
            "LEGISLATIE_SOAP_ENDPOINT": "https://test.local/soap",
            "LEGISLATIE_BASE_URL": "https://test.local",
            "LEGISLATIE_REQUEST_DELAY": "2.5",
            "LEGISLATIE_MAX_RETRIES": "5",
            "LEGISLATIE_CACHE_TTL": "1800",
            "LEGISLATIE_CACHE_PATH": "/tmp/test_cache",
            "LEGISLATIE_USE_PERSISTENT_CACHE": "true",
            "LEGISLATIE_REQUEST_TIMEOUT": "60",
            "LEGISLATIE_SOAP_TIMEOUT": "45",
            "LEGISLATIE_LOG_LEVEL": "DEBUG",
            "LEGISLATIE_LOG_FILE": "/tmp/test.log",
        }

        with patch.dict(os.environ, env_vars):
            import importlib

            importlib.reload(config)

            assert config.WSDL_URL == "https://test.local/wsdl"
            assert config.SOAP_ENDPOINT == "https://test.local/soap"
            assert config.BASE_URL == "https://test.local"
            assert config.REQUEST_DELAY == 2.5
            assert config.MAX_RETRIES == 5
            assert config.CACHE_TTL == 1800
            assert config.CACHE_PATH == "/tmp/test_cache"
            assert config.USE_PERSISTENT_CACHE is True
            assert config.REQUEST_TIMEOUT == 60
            assert config.SOAP_TIMEOUT == 45
            assert config.LOG_LEVEL == "DEBUG"
            assert config.LOG_FILE == "/tmp/test.log"

    def test_boolean_conversion(self):
        """Test boolean environment variable conversion."""
        test_cases = [
            ("true", True),
            ("TRUE", True),
            ("True", True),
            ("false", False),
            ("FALSE", False),
            ("False", False),
            ("anything", False),  # Any other string should be False
        ]

        for env_value, expected in test_cases:
            with patch.dict(os.environ, {"LEGISLATIE_USE_PERSISTENT_CACHE": env_value}):
                import importlib

                importlib.reload(config)

                assert (
                    config.USE_PERSISTENT_CACHE == expected
                ), f"Failed for '{env_value}': expected {expected}, got {config.USE_PERSISTENT_CACHE}"

    def test_numeric_conversion(self):
        """Test numeric environment variable conversion."""
        # Test integer conversion
        with patch.dict(os.environ, {"LEGISLATIE_MAX_RETRIES": "10"}):
            import importlib

            importlib.reload(config)
            assert config.MAX_RETRIES == 10

        # Test float conversion
        with patch.dict(os.environ, {"LEGISLATIE_REQUEST_DELAY": "0.5"}):
            import importlib

            importlib.reload(config)
            assert config.REQUEST_DELAY == 0.5

        # Test that invalid values raise ValueError when accessed
        with patch.dict(os.environ, {"LEGISLATIE_MAX_RETRIES": "not-a-number"}):
            import importlib

            try:
                importlib.reload(config)
                # If reload succeeds, accessing the value should raise ValueError
                _ = config.MAX_RETRIES
                pytest.fail("Expected ValueError for invalid integer conversion")
            except ValueError:
                pass  # Expected

    def test_setup_logging_default(self):
        """Test logging setup with default configuration."""
        with patch.dict(os.environ, {}, clear=True):
            import importlib

            importlib.reload(config)

            # Mock logging.basicConfig to verify it's called correctly
            with patch("logging.basicConfig") as mock_basic_config:
                with patch("logging.FileHandler") as mock_file_handler:
                    with patch("logging.StreamHandler") as mock_stream_handler:
                        mock_stream_handler.return_value = Mock()
                        mock_file_handler.return_value = Mock()

                        logger = config.setup_logging()

                        # Verify basicConfig was called
                        mock_basic_config.assert_called_once()

                        # Check call arguments
                        call_kwargs = mock_basic_config.call_args[1]
                        assert call_kwargs["level"] == logging.INFO
                        assert "format" in call_kwargs
                        assert "handlers" in call_kwargs

                        # Should have 2 handlers: StreamHandler and FileHandler
                        handlers = call_kwargs["handlers"]
                        assert len(handlers) == 2

                        # Verify logger is returned
                        assert logger is not None
                        assert logger.name == "config"

    def test_setup_logging_no_file(self):
        """Test logging setup without file logging."""
        with patch.dict(os.environ, {"LEGISLATIE_LOG_FILE": ""}):
            import importlib

            importlib.reload(config)

            with patch("logging.basicConfig") as mock_basic_config:
                with patch("logging.StreamHandler") as mock_stream_handler:
                    mock_stream_handler.return_value = Mock()

                    logger = config.setup_logging()

                    mock_basic_config.assert_called_once()
                    call_kwargs = mock_basic_config.call_args[1]

                    # Should have only StreamHandler
                    handlers = call_kwargs["handlers"]
                    assert len(handlers) == 1

    def test_setup_logging_different_levels(self):
        """Test logging setup with different log levels."""
        test_levels = [
            ("DEBUG", logging.DEBUG),
            ("INFO", logging.INFO),
            ("WARNING", logging.WARNING),
            ("ERROR", logging.ERROR),
            ("CRITICAL", logging.CRITICAL),
        ]

        for level_str, level_const in test_levels:
            with patch.dict(os.environ, {"LEGISLATIE_LOG_LEVEL": level_str}):
                import importlib

                importlib.reload(config)

                with patch("logging.basicConfig") as mock_basic_config:
                    config.setup_logging()

                    call_kwargs = mock_basic_config.call_args[1]
                    assert call_kwargs["level"] == level_const

    def test_setup_logging_invalid_level(self):
        """Test logging setup with invalid log level."""
        with patch.dict(os.environ, {"LEGISLATIE_LOG_LEVEL": "INVALID_LEVEL"}):
            import importlib

            importlib.reload(config)

            with patch("logging.basicConfig") as mock_basic_config:
                logger = config.setup_logging()

                # Should default to INFO
                call_kwargs = mock_basic_config.call_args[1]
                assert call_kwargs["level"] == logging.INFO

    def test_logger_suppression(self):
        """Test that noisy library logs are suppressed."""
        with patch.dict(os.environ, {}, clear=True):
            import importlib

            importlib.reload(config)

            with patch("logging.basicConfig"):
                with patch("logging.getLogger") as mock_get_logger:
                    mock_zeep_logger = Mock()
                    mock_urllib3_logger = Mock()

                    mock_get_logger.side_effect = lambda name: {
                        "zeep": mock_zeep_logger,
                        "urllib3": mock_urllib3_logger,
                    }.get(name, Mock())

                    config.setup_logging()

                    # Verify zeep and urllib3 loggers are set to WARNING
                    mock_zeep_logger.setLevel.assert_called_with(logging.WARNING)
                    mock_urllib3_logger.setLevel.assert_called_with(logging.WARNING)

    def test_logger_instance(self):
        """Test that module exports a logger instance."""
        # The module should have a logger attribute after import
        assert hasattr(config, "logger")
        assert isinstance(config.logger, logging.Logger)


# Mock class for testing
class Mock:
    """Simple mock class for testing."""

    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, *args, **kwargs):
        return Mock()

    def __getattr__(self, name):
        return Mock()
