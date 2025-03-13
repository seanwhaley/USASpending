"""Tests for logging configuration."""
import pytest
import logging
import os
import tempfile
from src.usaspending.core.logging_config import (
    configure_logging,
    get_logger,
    LogLevel
)

@pytest.fixture
def temp_log_dir():
    with tempfile.TemporaryDirectory() as tmpdirname:
        yield tmpdirname

def test_get_logger():
    """Test logger creation."""
    logger = get_logger(__name__)
    assert isinstance(logger, logging.Logger)
    assert logger.name == __name__

def test_configure_logging(temp_log_dir):
    """Test logging configuration."""
    log_file = os.path.join(temp_log_dir, 'test.log')
    
    # Configure logging
    configure_logging(
        log_file=log_file,
        log_level=LogLevel.DEBUG,
        console_level=LogLevel.INFO
    )
    
    # Get a test logger
    logger = get_logger('test_logger')
    
    # Test logging
    test_message = 'Test log message'
    logger.info(test_message)
    
    # Verify log file was created and contains message
    assert os.path.exists(log_file)
    with open(log_file, 'r') as f:
        log_content = f.read()
    assert test_message in log_content

def test_log_levels(temp_log_dir):
    """Test different logging levels."""
    log_file = os.path.join(temp_log_dir, 'test_levels.log')
    
    # Configure with INFO level
    configure_logging(
        log_file=log_file,
        log_level=LogLevel.INFO,
        console_level=LogLevel.INFO
    )
    
    logger = get_logger('test_levels')
    
    # Debug shouldn't be logged
    logger.debug('Debug message')
    # Info and above should be logged
    logger.info('Info message')
    logger.warning('Warning message')
    logger.error('Error message')
    
    with open(log_file, 'r') as f:
        log_content = f.read()
    
    assert 'Debug message' not in log_content
    assert 'Info message' in log_content
    assert 'Warning message' in log_content
    assert 'Error message' in log_content

def test_logger_inheritance():
    """Test logger inheritance behavior."""
    parent_logger = get_logger('parent')
    child_logger = get_logger('parent.child')
    
    assert child_logger.parent == parent_logger
    assert child_logger.level == parent_logger.level
