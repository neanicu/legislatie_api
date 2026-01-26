"""
Configuration management for Legislatie API Client.
Uses environment variables with fallback defaults.
"""

import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# SOAP API Configuration
WSDL_URL = os.getenv(
    "LEGISLATIE_WSDL_URL", "https://legislatie.just.ro/apiws/FreeWebService.svc?wsdl"
)
SOAP_ENDPOINT = os.getenv(
    "LEGISLATIE_SOAP_ENDPOINT",
    "https://legislatie.just.ro/apiws/FreeWebService.svc/SOAP",
)

# Scraper Configuration
BASE_URL = os.getenv("LEGISLATIE_BASE_URL", "https://legislatie.just.ro")
REQUEST_DELAY = float(os.getenv("LEGISLATIE_REQUEST_DELAY", "1.0"))
MAX_RETRIES = int(os.getenv("LEGISLATIE_MAX_RETRIES", "3"))

# Cache Configuration
CACHE_TTL = int(os.getenv("LEGISLATIE_CACHE_TTL", "3600"))  # seconds
CACHE_PATH = os.getenv("LEGISLATIE_CACHE_PATH", "./.legislatie_cache")
USE_PERSISTENT_CACHE = (
    os.getenv("LEGISLATIE_USE_PERSISTENT_CACHE", "false").lower() == "true"
)

# Timeout Configuration
REQUEST_TIMEOUT = int(os.getenv("LEGISLATIE_REQUEST_TIMEOUT", "30"))
SOAP_TIMEOUT = int(os.getenv("LEGISLATIE_SOAP_TIMEOUT", "30"))

# Logging Configuration
LOG_LEVEL = os.getenv("LEGISLATIE_LOG_LEVEL", "INFO").upper()
LOG_FILE = os.getenv("LEGISLATIE_LOG_FILE", "./legislatie.log")


# Configure logging
def setup_logging():
    """Configure logging based on environment settings."""
    log_level = getattr(logging, LOG_LEVEL, logging.INFO)

    handlers = [logging.StreamHandler()]
    if LOG_FILE:
        handlers.append(logging.FileHandler(LOG_FILE, encoding="utf-8"))

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
    )

    # Suppress noisy library logs
    logging.getLogger("zeep").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    return logging.getLogger(__name__)


# Export a default logger instance
logger = setup_logging()
