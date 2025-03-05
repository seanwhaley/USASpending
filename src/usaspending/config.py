"""Configuration management system."""
from typing import Dict, Any, Optional, List
from pathlib import Path
import os
import copy
import msvcrt  # For Windows

# Only import fcntl on Unix systems
if os.name != 'nt':
    import fcntl

from .exceptions import ConfigurationError
from .logging_config import get_logger
from .config_validation import validate_configuration
from .config_schemas import ROOT_CONFIG_SCHEMA
from .validation_manager import ValidationManager

logger = get_logger(__name__)

class ConfigManager:
    """Manages configuration loading and access with validation."""

    def __init__(self, config_path: str):
        """Initialize configuration manager."""
        self.config_path = config_path
        self._config: Dict[str, Any] = {}
        self.validation_manager = None
        self._load_configuration()

    def _load_configuration(self) -> None:
        """Load and validate the configuration."""
        try:
            # Validate configuration
            errors = validate_configuration(self.config_path, ROOT_CONFIG_SCHEMA)
            if errors:
                error_msg = "Configuration validation failed:\n" + "\n".join(
                    f"[{e.severity}] {e.path}: {e.message}" for e in errors
                )
                raise ConfigurationError(error_msg)
            
            # Load configuration after validation
            with open(self.config_path, 'r') as f:
                import yaml
                self._config = yaml.safe_load(f)

            # Initialize validation manager
            self.validation_manager = ValidationManager(self._config)
            
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration: {str(e)}")

    def get_config(self) -> Dict[str, Any]:
        """Get complete configuration dictionary."""
        return copy.deepcopy(self._config)

    def get_entity_types(self) -> List[str]:
        """Get configured entity types."""
        return list(self._config.get('entities', {}).keys())

    def get_paths(self) -> Dict[str, str]:
        """Get configured paths."""
        return self._config.get('paths', {})
    
    def get_entity_config(self, entity_type: str) -> Dict[str, Any]:
        """Get configuration for an entity type."""
        entities = self._config.get('entities', {})
        if entity_type not in entities:
            raise ConfigurationError(f"No configuration found for entity type: {entity_type}")
        return copy.deepcopy(entities[entity_type])

    def get_system_config(self) -> Dict[str, Any]:
        """Get system configuration settings."""
        return self._config.get('system', {})

    def get_validation_rules(self, group_id: str) -> List[str]:
        """Get validation rules for a validation group."""
        if not self.validation_manager:
            return []
        return self.validation_manager.get_group_rules(group_id)

    def get_field_dependencies(self, field: str) -> List[str]:
        """Get dependencies for a field."""
        if not self.validation_manager:
            return []
        deps = self.validation_manager.get_field_dependencies(field)
        return [dep.target_field for dep in deps]

    def get_validation_order(self) -> List[str]:
        """Get fields in dependency-aware validation order."""
        if not self.validation_manager:
            return []
        return self.validation_manager.get_validation_order()

def atomic_file_operation(file_path: Path, operation: callable):
    """Execute file operation with proper locking."""
    try:
        with open(file_path, 'r+' if os.path.exists(file_path) else 'w+') as f:
            # Apply file locking based on platform
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

# ConfigManager singleton provides all needed functionality
__all__ = ['ConfigManager', 'atomic_file_operation']