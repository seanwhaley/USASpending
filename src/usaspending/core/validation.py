"""Core validation functionality."""
from typing import Dict, Any, Optional, List, Set, Type
from abc import ABC, abstractmethod
import logging
from .interfaces import IValidationMediator
from .types import ValidationRule, RuleSet
from .exceptions import ValidationError
from .utils import safe_operation

logger = logging.getLogger(__name__)

class BaseValidator(ABC):
    """Abstract base class for validation."""

    def __init__(self) -> None:
        """Initialize validator."""
        self._rules: List[ValidationRule] = []
        self._errors: List[str] = []
        self._initialized: bool = False
        self._enabled: bool = True
        self._rule_sets: Dict[str, RuleSet] = {}

    @abstractmethod
    def add_validation_rule(self, rule: ValidationRule) -> None:
        """Add a validation rule."""
        raise NotImplementedError

    @abstractmethod
    def remove_validation_rule(self, rule_id: str) -> None:
        """Remove a validation rule."""
        raise NotImplementedError

    def validate(self, entity_id: str, data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> bool:
        """Base validation method, to be extended by subclasses."""
        try:
            if not data:
                self._errors.append(f"No data provided for validation of {entity_id}")
                return False
                
            # Default validation just checks data is not empty
            return True
            
        except Exception as e:
            self._errors.append(f"Validation error: {str(e)}")
            return False
            
    def get_errors(self) -> List[str]:
        """Get validation error messages."""
        return self._errors.copy()

    def clear_errors(self) -> None:
        """Clear validation errors."""
        self._errors.clear()

    def get_rule_sets(self) -> Dict[str, RuleSet]:
        """Get all registered rule sets."""
        return self._rule_sets.copy()

    def is_enabled(self) -> bool:
        """Check if validator is enabled."""
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        """Set validator enabled state."""
        self._enabled = enabled

    def is_initialized(self) -> bool:
        """Check if validator is initialized."""
        return self._initialized

    def cleanup(self) -> None:
        """Clean up resources."""
        self._rules.clear()
        self._errors.clear()
        self._rule_sets.clear()
        self._initialized = False

    def add_error(self, error_message: str) -> None:
        """Add a validation error message.
        
        Args:
            error_message: The error message to add
        """
        self._errors.append(error_message)

class ValidationService(BaseValidator):
    """Core validation service implementation."""
    
    def __init__(self, mediator: IValidationMediator) -> None:
        """Initialize validation service."""
        super().__init__()
        self._mediator = mediator
        self._rule_sets: Dict[str, RuleSet] = {}
        self._initialized = False
        
    def add_validation_rule(self, rule: ValidationRule) -> None:
        """Add a validation rule."""
        if rule.field_name not in self._rule_sets:
            self._rule_sets[rule.field_name] = RuleSet(rule.field_name, [])
        self._rule_sets[rule.field_name].rules.append(rule)

    def remove_validation_rule(self, rule_id: str) -> None:
        """Remove a validation rule."""
        for rule_set in self._rule_sets.values():
            rule_set.rules = [r for r in rule_set.rules if r.id != rule_id]

    @safe_operation
    def validate(self, entity_id: str, data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> bool:
        """Validate data using mediator and rule sets."""
        if not self._mediator:
            self._errors.append("No validation mediator configured")
            return False
            
        validation_context = context or {}
        validation_context.update({'entity_type': entity_id})
        
        # Run entity-level validation through mediator
        if not self._mediator.validate_entity(entity_id, data, validation_context):
            self._errors.extend(self._mediator.get_validation_errors())
            return False
            
        # Apply rule sets for each field
        for field_name, value in data.items():
            if not self.validate_field(field_name, value, validation_context):
                return False

        return True

    def validate_field(self, field_name: str, value: Any, context: Optional[Dict[str, Any]] = None) -> bool:
        """Validate a single field."""
        try:
            # Apply field-specific rule set if it exists
            rule_set = self._rule_sets.get(field_name)
            if rule_set and rule_set.enabled:
                for rule in rule_set.rules:
                    if not self._validate_rule(value, rule, context):
                        return False
                        
            # Run validation through mediator
            if self._mediator and not self._mediator.validate_field(field_name, value, context):
                self._errors.extend(self._mediator.get_validation_errors())
                return False
                
            return True
            
        except Exception as e:
            self._errors.append(f"Field validation error for {field_name}: {str(e)}")
            return False

    def _validate_rule(self, value: Any, rule: ValidationRule, context: Optional[Dict[str, Any]] = None) -> bool:
        """Apply a single validation rule."""
        if not rule.enabled:
            return True
            
        try:
            # Instead of using validate_rule directly, use validate_field with rule context
            rule_context = context or {}
            rule_context.update({
                'rule_id': rule.id,
                'rule_type': rule.rule_type,
                'parameters': rule.parameters
            })
            
            if not self._mediator.validate_field(rule.field_name, value, rule_context):
                self._errors.extend(self._mediator.get_validation_errors())
                return False
                
            return True
            
        except Exception as e:
            self._errors.append(f"Rule validation error: {str(e)}")
            return False

    def register_rule_set(self, field_name: str, rule_set: RuleSet) -> None:
        """Register a validation rule set for a field."""
        self._rule_sets[field_name] = rule_set
        # Register rules with the mediator
        self._mediator.register_rules(field_name, rule_set.rules)

    def get_rule_set(self, field_name: str) -> Optional[RuleSet]:
        """Get validation rule set for a field."""
        return self._rule_sets.get(field_name)

    def cleanup(self) -> None:
        """Clean up resources."""
        self._rule_sets.clear()
        self._errors.clear()
        self._initialized = False

__all__ = ['BaseValidator', 'ValidationService']