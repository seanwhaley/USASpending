"""USASpending data processing package."""
from typing import Dict, Any, List, Optional, Type, TypeVar
import importlib
import logging

# Centralize common utility functions and classes
from .exceptions import ConfigurationError
from .logging_config import get_logger
from .file_utils import ensure_directory

# Re-export component utilities
from .component_utils import (
    create_component,
    create_component_from_config, 
    create_components_from_config,
    implements,
    implements_interface
)

# Re-export main classes
from .entity_factory import EntityFactory
from .entity_store import EntityStore, FileSystemEntityStore
from .validation_service import ValidationService

# Alias ensure_directory to match expected name
ensure_directory_exists = ensure_directory

__all__ = [
    # Utility functions
    'get_logger',
    'create_component',
    'create_component_from_config',
    'create_components_from_config',
    'implements',
    'implements_interface',
    'ensure_directory_exists',
    
    # Exceptions
    'ConfigurationError',
    
    # Main classes
    'EntityFactory',
    'EntityStore',
    'FileSystemEntityStore',
    'ValidationService',
]