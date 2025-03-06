"""Validation framework for entity data."""
from typing import Dict, Any, List, Optional, Callable

from . import (
    get_logger, ValidationService, ConfigurationError,
    create_component_from_config
)
from .interfaces import IValidationService, ISchemaAdapter, IDependencyManager

logger = get_logger(__name__)

from dataclasses import dataclass, field
from collections import defaultdict

@dataclass
class ValidationRule:
    """Configuration for a validation rule."""
    rule_type: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    error_message: str = ""
    severity: str = "error"
    dependencies: List[str] = field(default_factory=list)

class ValidationServiceBuilder:
    """Builder for creating configured ValidationService instances."""
    
    def __init__(self):
        """Initialize builder."""
        self.adapters: Dict[str, ISchemaAdapter] = {}
        self.dependency_manager: Optional[IDependencyManager] = None
        self.rules: Dict[str, List[ValidationRule]] = defaultdict(list)
        
    def with_adapter(self, field_name: str, adapter: ISchemaAdapter) -> 'ValidationServiceBuilder':
        """Add schema adapter."""
        self.adapters[field_name] = adapter
        return self
        
    def with_dependency_manager(self, manager: IDependencyManager) -> 'ValidationServiceBuilder':
        """Set dependency manager."""
        self.dependency_manager = manager
        return self
        
    def with_rule(self, field_name: str, rule: ValidationRule) -> 'ValidationServiceBuilder':
        """Add validation rule."""
        self.rules[field_name].append(rule)
        return self
        
    def build(self) -> ValidationService:
        """Create ValidationService instance."""
        if not self.dependency_manager:
            raise ValueError("Dependency manager is required")
            
        service = ValidationService(self.dependency_manager)
        
        # Register adapters
        for field_name, adapter in self.adapters.items():
            service.adapters[field_name] = adapter
            
        # Add validation rules
        for field_name, rules in self.rules.items():
            for rule in rules:
                rule_id = f"{field_name}.{rule.rule_type}"
                service.add_rule(rule_id, rule.__dict__)
                
        return service