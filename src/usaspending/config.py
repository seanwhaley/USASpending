"""Configuration management for data processing and validation."""

import os
import yaml
import json
import jsonschema
from typing import Any, Dict, Optional

from src.usaspending.logging_config import get_logger
from src.usaspending.config_schema import ROOT_CONFIG_SCHEMA

logger = get_logger(__name__)

class ConfigManager:
    """Manages configuration loading and validation."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize configuration manager."""
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        
    def load(self, config_path: Optional[str] = None) -> None:
        """Load configuration from YAML file.
        
        Args:
            config_path: Optional override path to config file
        """
        if config_path:
            self.config_path = config_path
            
        if not self.config_path:
            raise ValueError("No configuration path specified")
            
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
            
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
            logger.info(f"Loaded configuration from {self.config_path}")
            self.validate()
        except Exception as e:
            logger.error(f"Failed to load configuration: {str(e)}")
            raise
            
    def validate(self) -> None:
        """Validate loaded configuration against schema."""
        try:
            jsonschema.validate(self.config, ROOT_CONFIG_SCHEMA)
            logger.info("Configuration validation successful")
        except jsonschema.exceptions.ValidationError as e:
            logger.error(f"Invalid configuration: {str(e)}")
            raise
            
    def get(self, *keys: str, default: Any = None) -> Any:
        """Get nested configuration value using dot notation."""
        result = self.config
        for key in keys:
            if isinstance(result, dict):
                result = result.get(key, default)
            else:
                return default
        return result
        
    def get_entity_config(self, entity_name: str) -> Dict[str, Any]:
        """Get configuration for a specific entity.
        
        Args:
            entity_name: Name of entity to get configuration for
            
        Returns:
            Entity configuration dictionary
        """
        if not self.config:
            raise ValueError("Configuration not loaded")
            
        entities = self.config.get('entities', {})
        if entity_name not in entities:
            raise KeyError(f"No configuration found for entity: {entity_name}")
            
        return entities[entity_name]
        
    def get_field_properties(self, field_name: str) -> Dict[str, Any]:
        """Get properties for a specific field.
        
        Args:
            field_name: Name of field to get properties for
            
        Returns:
            Field properties dictionary
        """
        if not self.config:
            raise ValueError("Configuration not loaded")
            
        properties = self.config.get('field_properties', {})
        
        # Check for exact match first
        for category in properties.values():
            for field_type, config in category.items():
                if field_name in config.get('fields', []):
                    return config
                    
        # Then check patterns
        for category in properties.values():
            for field_type, config in category.items():
                for pattern in config.get('fields', []):
                    if '*' in pattern:
                        import fnmatch
                        if fnmatch.fnmatch(field_name, pattern):
                            return config
                            
        return {}

    def get_config(self) -> Dict[str, Any]:
        """Get the complete configuration.
        
        Returns:
            The complete configuration dictionary
        """
        if not self.config:
            raise ValueError("Configuration not loaded")
        return self.config

import logging
import copy
import msvcrt  # For Windows
from pathlib import Path
from typing import TypeVar, Type
from dataclasses import dataclass
from datetime import datetime

# Only import fcntl on Unix systems
if os.name != 'nt':
    import fcntl

from .exceptions import ConfigurationError
from .types import ValidationResult

T = TypeVar('T')

def atomic_file_operation(file_path: Path, operation: callable):
    """Execute file operation with proper locking."""
    try:
        with open(file_path, 'r+' if os.path.exists(file_path) else 'w+') as f:
            if os.name == 'nt':  # Windows
                try:
                    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError as e:
                    # Handle case where file is already locked
                    logger.error(f"File is locked: {e}")
                    raise ConfigurationError(f"File is locked: {e}") from e
            elif 'fcntl' in globals():  # Unix
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            
            try:
                return operation(f)
            finally:
                if os.name == 'nt':
                    try:
                        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                    except OSError:
                        pass  # Ignore errors during unlock
                elif 'fcntl' in globals():
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    except IOError as e:
        logger.error(f"File operation failed: {e}")
        raise ConfigurationError(f"File operation failed: {e}") from e

@dataclass
class CachedValidation:
    """Represents a cached validation result."""
    timestamp: datetime
    result: ValidationResult

    def get(self, *keys: str, default: Any = None) -> Any:
        """Get nested configuration value using dot notation."""
        result = self.config
        for key in keys:
            if isinstance(result, dict):
                result = result.get(key, default)
            else:
                return default
        return result

    def reload(self) -> None:
        """Reload configuration from file."""
        logger.debug("Reloading configuration from file")
        self.config = self._load_config(self.config_path)
        self._validate_config()

    def get_typed(self, *keys: str, type_: Type[T], default: T = None) -> T:
        """Get configuration value with type coercion."""
        value = self.get(*keys, default=default)
        if value is None:
            return default
        try:
            return type_(value)
        except (ValueError, TypeError) as e:
            logger.error(f"Failed to convert configuration value at {'.'.join(keys)} to {type_.__name__}: {str(e)}")
            raise ConfigurationError(
                f"Failed to convert configuration value at {'.'.join(keys)} to {type_.__name__}: {str(e)}"
            )

    def get_config(self) -> Dict[str, Any]:
        """Get the complete configuration.
        
        Returns:
            The complete configuration dictionary
        """
        return self.config

# Function for processor.py to use
def convert_csv_to_json(config_manager: ConfigManager) -> bool:
    try:
        # Access the configuration using the get_config method
        config_data = config_manager.get_config()
        
        # Ensure input and output paths are correct
        input_file = Path(config_data['system']['io']['input']['file'])
        output_dir = Path(config_data['system']['io']['output']['directory'])

        if not input_file.exists():
            logger.error(f"Input file does not exist: {input_file}")
            return False

        # Perform the conversion (dummy implementation for illustration)
        output_file = output_dir / (input_file.stem + '.json')
        with input_file.open('r', encoding='utf-8') as csv_file:
            csv_data = csv_file.read()
            # Dummy conversion logic
            json_data = {"data": csv_data}
            with output_file.open('w', encoding='utf-8') as json_file:
                json.dump(json_data, json_file)

        logger.info(f"Conversion successful: {output_file}")
        return True

    except Exception as e:
        logger.error(f"Conversion failed: {str(e)}")
        logger.debug("Stack trace:", exc_info=True)
        return False

# ConfigManager singleton provides all needed functionality
__all__ = ['ConfigManager', 'convert_csv_to_json']