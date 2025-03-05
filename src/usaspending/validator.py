"""Validation system for data records."""
from typing import Dict, Any, List, Optional, Set, Callable
from dataclasses import dataclass, field
from collections import defaultdict

from .interfaces import IValidationService, ISchemaAdapter, IDependencyManager
from .logging_config import get_logger

logger = get_logger(__name__)

@dataclass
class ValidationRule:
    """Configuration for a validation rule."""
    rule_type: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    error_message: str = ""
    severity: str = "error"
    dependencies: List[str] = field(default_factory=list)

class ValidationService(IValidationService):
    """Validates data records using configured rules and adapters."""
    
    def __init__(self, adapters: Dict[str, ISchemaAdapter], 
                 dependency_manager: IDependencyManager):
        """Initialize validation service."""
        self.adapters = adapters
        self.dependency_manager = dependency_manager
        self.rules: Dict[str, List[ValidationRule]] = defaultdict(list)
        self.stats: Dict[str, int] = defaultdict(int)
        self.validation_errors: List[str] = []
        
    def add_rule(self, field_name: str, rule: ValidationRule) -> None:
        """Add a validation rule for a field."""
        self.rules[field_name].append(rule)
        
        # Register dependencies if any
        if rule.dependencies:
            for dep in rule.dependencies:
                self.dependency_manager.add_dependency(
                    field_name=field_name,
                    target_field=dep,
                    dependency_type=rule.rule_type,
                    validation_rule=rule.parameters
                )
        
    def validate_field(self, field_name: str, value: Any) -> List[str]:
        """Validate a single field value."""
        self.validation_errors.clear()
        self.stats['total_field_validations'] += 1
        
        # Apply schema validation if adapter exists
        if field_name in self.adapters:
            adapter = self.adapters[field_name]
            if not adapter.validate(value, field_name):
                self.validation_errors.extend(adapter.get_validation_errors())
                self.stats['schema_validation_errors'] += len(adapter.get_validation_errors())
        
        # Apply custom validation rules
        for rule in self.rules.get(field_name, []):
            if not self._validate_rule(value, rule):
                if rule.error_message:
                    self.validation_errors.append(rule.error_message)
                self.stats['rule_validation_errors'] += 1
        
        return self.validation_errors.copy()
        
    def validate_record(self, record: Dict[str, Any]) -> List[str]:
        """Validate an entire record."""
        self.validation_errors.clear()
        self.stats['total_record_validations'] += 1
        
        # Get validation order considering dependencies
        validation_order = self.dependency_manager.get_validation_order()
        
        # Validate fields in order
        for field_name in validation_order:
            if field_name not in record:
                continue
                
            # Validate dependencies first
            dependency_errors = self.dependency_manager.validate_dependencies(record, self.adapters)
            if dependency_errors:
                self.validation_errors.extend(dependency_errors)
                self.stats['dependency_validation_errors'] += len(dependency_errors)
                continue
            
            # Validate the field itself
            field_errors = self.validate_field(field_name, record[field_name])
            if field_errors:
                self.validation_errors.extend(field_errors)
        
        return self.validation_errors.copy()
        
    def get_validation_stats(self) -> Dict[str, Any]:
        """Get validation statistics."""
        return dict(self.stats)
        
    def _validate_rule(self, value: Any, rule: ValidationRule) -> bool:
        """Validate a value against a rule."""
        try:
            if rule.rule_type == "required":
                return value is not None and str(value).strip() != ""
                
            elif rule.rule_type == "pattern":
                import re
                pattern = rule.parameters.get("pattern", "")
                if not pattern:
                    return True
                return bool(re.match(pattern, str(value)))
                
            elif rule.rule_type == "range":
                if value is None:
                    return True
                min_val = rule.parameters.get("min")
                max_val = rule.parameters.get("max")
                if min_val is not None and value < min_val:
                    return False
                if max_val is not None and value > max_val:
                    return False
                return True
                
            elif rule.rule_type == "length":
                if value is None:
                    return True
                min_len = rule.parameters.get("min")
                max_len = rule.parameters.get("max")
                value_len = len(str(value))
                if min_len is not None and value_len < min_len:
                    return False
                if max_len is not None and value_len > max_len:
                    return False
                return True
                
            elif rule.rule_type == "enum":
                if value is None:
                    return True
                allowed_values = rule.parameters.get("values", [])
                return value in allowed_values
                
            elif rule.rule_type == "custom":
                validator = rule.parameters.get("validator")
                if not validator or not callable(validator):
                    return True
                return validator(value)
                
            return True
            
        except Exception as e:
            logger.error(f"Validation error for rule {rule.rule_type}: {e}")
            return False

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
            
        service = ValidationService(self.adapters, self.dependency_manager)
        for field_name, rules in self.rules.items():
            for rule in rules:
                service.add_rule(field_name, rule)
                
        return service