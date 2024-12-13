"""
Test package initialization module for the Specification Management API.

This module configures the test environment settings and provides common test utilities.
It ensures consistent test configuration across all test modules and sets up appropriate
logging for test execution.

Version: 1.0
"""

import logging
import pytest
from config.settings import TESTING

# Test environment configuration
TEST_ENV: bool = True

# Configure test logging level
TEST_LOG_LEVEL: int = logging.DEBUG

def configure_test_logging() -> None:
    """
    Configure logging settings for the test environment.
    
    This function sets up logging with appropriate formatting and level for test execution.
    It configures:
    - Debug level logging for detailed test output
    - Consistent log format for test result analysis
    - Independent logging for test execution
    
    Returns:
        None
    """
    # Create logger for tests
    test_logger = logging.getLogger('test')
    test_logger.setLevel(TEST_LOG_LEVEL)
    
    # Prevent log propagation to parent loggers
    test_logger.propagate = False
    
    # Create console handler with formatting
    console_handler = logging.StreamHandler()
    console_handler.setLevel(TEST_LOG_LEVEL)
    
    # Define log format for tests
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(formatter)
    
    # Add handler to logger
    test_logger.addHandler(console_handler)

# Verify test environment
assert TESTING is True, "Test environment not properly configured"

# Initialize test logging
configure_test_logging()

# Export test environment configuration
__all__ = [
    'TEST_ENV',
    'configure_test_logging',
]