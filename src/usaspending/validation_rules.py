"""Validation rule loading and management."""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import yaml
from .logging_config import get_logger

logger = get_logger(__name__)

@dataclass
class ValidationRule:
    """Represents a validation rule with configuration."""
    field: str
    rule_type: str
    params: Dict[str, Any]
    error_message: Optional[str] = None
    dependencies: Optional[List[str]] = None
    
    @classmethod
    def from_yaml(cls, config: Dict[str, Any]) -> 'ValidationRule':
        """Create validation rule from YAML configuration."""
        return cls(
            field=config['field'],
            rule_type=config['type'],
            params=config.get('parameters', {}),
            error_message=config.get('error_message'),
            dependencies=config.get('dependencies', [])
        )

class ValidationRuleLoader:
    """Loads and manages validation rules."""
    
    def __init__(self):
        """Initialize rule loader."""
        self.rules: Dict[str, List[ValidationRule]] = {}
        self.errors: List[str] = []
        
    def load_rules(self, config: Dict[str, Any]) -> None:
        """Load validation rules from configuration.
        
        Args:
            config: Configuration dictionary containing validation rules
        """
        validation_config = config.get('validation_types', {})
        
        for entity_type, rules in validation_config.items():
            self.rules[entity_type] = []
            for rule_config in rules:
                try:
                    rule = ValidationRule.from_yaml(rule_config)
                    self.rules[entity_type].append(rule)
                except Exception as e:
                    error_msg = f"Error loading validation rule for {entity_type}: {e}"
                    self.errors.append(error_msg)
                    logger.error(error_msg)
                    
    def get_rules(self, entity_type: str) -> List[ValidationRule]:
        """Get validation rules for an entity type.
        
        Args:
            entity_type: Type of entity to get rules for
            
        Returns:
            List of validation rules for the entity type
        """
        return self.rules.get(entity_type, []).copy()
        
    def get_errors(self) -> List[str]:
        """Get any errors that occurred during rule loading."""
        return self.errors.copy()
        
    def get_dependencies(self, entity_type: str, field: str) -> List[str]:
        """Get dependencies for a field in an entity type.
        
        Args:
            entity_type: Type of entity
            field: Field name to get dependencies for
            
        Returns:
            List of field names that the given field depends on
        """
        for rule in self.rules.get(entity_type, []):
            if rule.field == field and rule.dependencies:
                return rule.dependencies
        return []