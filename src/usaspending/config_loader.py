"""Configuration loading and management."""
from typing import Dict, Any, Optional, List, Type, TypeVar
import yaml
import os
from pathlib import Path

from . import get_logger, create_component_from_config, ConfigurationError
from .validation_rules import ValidationRule, ValidationRuleLoader

logger = get_logger(__name__)

class ConfigLoader:
    """Loads and validates configuration without validation dependencies."""

    def __init__(self):
        """Initialize configuration loader."""
        self.config: Dict[str, Any] = {}
        self.validation_loader = ValidationRuleLoader()
        self.errors: List[str] = []

    def load_config(self, config_path: str) -> None:
        """Load configuration from YAML file.
        
        Args:
            config_path: Path to configuration file
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
            
            # Load validation rules
            self.validation_loader.load_rules(self.config)
            self.errors.extend(self.validation_loader.get_errors())

            # Basic validation of required sections
            self._validate_required_sections()

        except yaml.YAMLError as e:
            error_msg = f"Error parsing YAML configuration: {str(e)}"
            self.errors.append(error_msg)
            logger.error(error_msg)
        except Exception as e:
            error_msg = f"Error loading configuration: {str(e)}"
            self.errors.append(error_msg)
            logger.error(error_msg)

    def _validate_required_sections(self) -> None:
        """Validate that required configuration sections exist."""
        required_sections = {
            'paths',
            'entity_factory',
            'entity_store',
            'validation_service'
        }

        missing = required_sections - set(self.config.keys())
        if missing:
            error_msg = f"Missing required configuration sections: {', '.join(missing)}"
            self.errors.append(error_msg)
            logger.error(error_msg)

    def get_config(self) -> Dict[str, Any]:
        """Get the loaded configuration.
        
        Returns:
            Complete configuration dictionary
        """
        return self.config.copy()

    def get_validation_rules(self, entity_type: str) -> List[ValidationRule]:
        """Get validation rules for an entity type.
        
        Args:
            entity_type: Type of entity to get rules for
            
        Returns:
            List of validation rules for the entity type
        """
        return self.validation_loader.get_rules(entity_type)

    def get_errors(self) -> List[str]:
        """Get any errors that occurred during configuration loading."""
        return self.errors.copy()

    def get_field_dependencies(self, entity_type: str, field: str) -> List[str]:
        """Get dependencies for a field in an entity type.
        
        Args:
            entity_type: Type of entity
            field: Field name to get dependencies for
            
        Returns:
            List of field names that the given field depends on
        """
        return self.validation_loader.get_dependencies(entity_type, field)

    def get_entity_types(self) -> List[str]:
        """Get list of configured entity types.
        
        Returns:
            List of entity type names
        """
        return list(self.config.get('entities', {}).keys())

def load_components(config: Dict[str, Any]) -> Dict[str, Any]:
    """Load and initialize components from configuration."""
    components = {}
    
    # Load standard components in dependency order
    component_names = [
        'entity_factory',
        'entity_store',
        'validation_service'
    ]
    
    for name in component_names:
        try:
            if 'system' in config and name in config['system']:
                component_config = config['system'][name]
                components[name] = create_component_from_config(component_config, components)
            else:
                logger.warning(f"Component configuration missing for {name}")
        except Exception as e:
            logger.error(f"Error loading component {name}: {str(e)}")
            raise
            
    return components