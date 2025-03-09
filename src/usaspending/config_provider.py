"""Configuration provider implementation."""
from typing import Dict, Any, Optional, List
import logging
import yaml
from pathlib import Path
import copy

from .interfaces import IConfigurationProvider
from .exceptions import ConfigurationError

logger = logging.getLogger(__name__)


class ConfigurationProvider(IConfigurationProvider):
    """Manages configuration loading and validation."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize configuration provider.
        
        Args:
            config_path: Optional path to configuration file
        """
        self._config: Dict[str, Any] = {}
        self._errors: List[str] = []
        self._config_path = config_path
        
        if config_path:
            self.load_config(config_path)

    def load_config(self, config_path: str) -> None:
        """Load configuration from file.
        
        Args:
            config_path: Path to configuration file
        
        Raises:
            ConfigurationError: If config file cannot be loaded
        """
        try:
            path = Path(config_path)
            if not path.exists():
                raise ConfigurationError(f"Configuration file not found: {config_path}")
                
            with open(path, 'r') as f:
                self._config = yaml.safe_load(f)
                
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration: {str(e)}")

    def get_config(self, section: Optional[str] = None) -> Dict[str, Any]:
        """Get configuration data.
        
        Args:
            section: Optional section name to retrieve
            
        Returns:
            Configuration dictionary
        """
        if not section:
            return copy.deepcopy(self._config)
            
        return copy.deepcopy(self._config.get(section, {}))

    def validate_config(self) -> bool:
        """Validate configuration structure and contents.
        
        Returns:
            True if valid, False otherwise
        """
        self._errors.clear()
        
        try:
            # Validate required sections
            required_sections = {'validation_types', 'field_types', 'entities'}
            missing = required_sections - set(self._config.keys())
            if missing:
                self._errors.append(f"Missing required sections: {', '.join(missing)}")
                return False

            # Validate validation types
            validation_types = self._config.get('validation_types', {})
            if not isinstance(validation_types, dict):
                self._errors.append("validation_types must be a dictionary")
                return False
                
            for type_name, rules in validation_types.items():
                if not isinstance(rules, list):
                    self._errors.append(f"Rules for {type_name} must be a list")
                    return False
                    
                for rule in rules:
                    if not isinstance(rule, dict) or 'type' not in rule:
                        self._errors.append(f"Invalid rule in {type_name}: missing type")
                        return False

            # Validate field types
            field_types = self._config.get('field_types', {})
            if not isinstance(field_types, dict):
                self._errors.append("field_types must be a dictionary")
                return False

            # Validate entities
            entities = self._config.get('entities', {})
            if not isinstance(entities, dict):
                self._errors.append("entities must be a dictionary")
                return False
                
            for entity_name, entity_config in entities.items():
                if not isinstance(entity_config, dict):
                    self._errors.append(f"Invalid configuration for entity {entity_name}")
                    return False
                    
                if 'field_mappings' not in entity_config:
                    self._errors.append(f"Missing field_mappings for entity {entity_name}")
                    return False

            return True

        except Exception as e:
            self._errors.append(f"Configuration validation failed: {str(e)}")
            return False

    def get_validation_errors(self) -> List[str]:
        """Get configuration validation errors.
        
        Returns:
            List of validation error messages
        """
        return self._errors.copy()

    def get_entity_config(self, entity_type: str) -> Optional[Dict[str, Any]]:
        """Get configuration for specific entity type.
        
        Args:
            entity_type: Entity type to get configuration for
            
        Returns:
            Entity configuration dictionary or None if not found
        """
        return self.get_config('entities').get(entity_type)

    def get_validation_rules(self, validation_type: str) -> List[Dict[str, Any]]:
        """Get validation rules for a type.
        
        Args:
            validation_type: Type of validation rules to get
            
        Returns:
            List of validation rules
        """
        validation_types = self.get_config('validation_types')
        rules: List[Dict[str, Any]] = validation_types.get(validation_type, [])
        return rules