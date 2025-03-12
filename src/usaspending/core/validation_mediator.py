"""Validation mediator implementation."""
from typing import Dict, Any, List, Optional, Sequence, Union
from ..core.interfaces import IValidationMediator, IValidator
from ..core.types import ValidationRule, RuleSet, EntityType

class ValidationMediator(IValidationMediator):
    """Implementation of validation mediation."""

    def __init__(self) -> None:
        """Initialize validation mediator."""
        self._rule_sets: Dict[str, RuleSet] = {}
        self._validators: Dict[str, IValidator] = {}
        self._errors: List[str] = []
        self._stats = {
            'validated_fields': 0,
            'validation_errors': 0
        }

    def register_rules(self, field_name: str, rules: Sequence[ValidationRule]) -> None:
        """Register validation rules for a field."""
        rule_set = RuleSet(
            name=field_name,
            rules=list(rules)
        )
        self._rule_sets[field_name] = rule_set

    def register_validator(self, entity_type: Union[EntityType, str], validator: IValidator) -> None:
        """Register a validator for an entity type."""
        self._validators[str(entity_type)] = validator

    def validate(self, entity_type: Union[EntityType, str], data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> bool:
        """Validate entity data against rules."""
        self.clear_errors()
        context = context or {}
        
        entity_type_str = str(entity_type)
        
        # If we have a specific validator for this entity type, use it
        if entity_type_str in self._validators:
            validator = self._validators[entity_type_str]
            valid = validator.validate(entity_type_str, data, context)
            if hasattr(validator, 'get_errors'):
                self._errors.extend(validator.get_errors())
            return valid
            
        # Otherwise validate using field-level rules if applicable
        is_valid = True
        
        for field_name, value in data.items():
            if not self._validate_field(field_name, value, context):
                is_valid = False
                
        return is_valid

    def validate_entity(self, entity_type: str, data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> bool:
        """Validate a complete entity."""
        return self.validate(entity_type, data, context)

    def validate_field(self, field_name: str, value: Any, context: Optional[Dict[str, Any]] = None) -> bool:
        """Validate a single field value."""
        return self._validate_field(field_name, value, context or {})

    def _validate_field(self, field_name: str, value: Any, validation_context: Dict[str, Any]) -> bool:
        """Internal method to validate a field value using registered rules."""
        rule_set = self._rule_sets.get(field_name)
        if not rule_set:
            return True  # No rules to validate against

        is_valid = self._validate_against_ruleset(rule_set, value, validation_context)
        if not is_valid:
            self._stats['validation_errors'] += 1
        self._stats['validated_fields'] += 1
        
        return is_valid
        
    def _validate_against_ruleset(self, rule_set: RuleSet, value: Any, validation_context: Dict[str, Any]) -> bool:
        """Validate a value against rules in a ruleset."""
        if not rule_set:
            return True
            
        is_valid = True
        
        for rule in rule_set.rules:
            if not getattr(rule, 'enabled', True):
                continue
                
            # Basic validation logic for different rule types
            rule_type = rule.rule_type.value
            
            # Required field validation
            if rule_type == "required" and value is None:
                self._errors.append(rule.message or f"Field '{rule.field_name}' is required")
                is_valid = False
                continue
                
            # Skip other validations if value is None (unless it was required)
            if value is None:
                continue
                
            # Type validation
            if rule_type == "type":
                expected_type = rule.parameters.get("value")
                if expected_type and not self._check_type(value, expected_type):
                    self._errors.append(rule.message or f"Field '{rule.field_name}' must be of type {expected_type}")
                    is_valid = False
                    
            # Pattern validation
            elif rule_type == "pattern":
                pattern = rule.parameters.get("pattern")
                if pattern and not self._check_pattern(value, pattern):
                    self._errors.append(rule.message or f"Field '{rule.field_name}' must match pattern {pattern}")
                    is_valid = False
                    
            # Range validation
            elif rule_type == "range":
                min_val = rule.parameters.get("min")
                max_val = rule.parameters.get("max")
                if not self._check_range(value, min_val, max_val):
                    self._errors.append(rule.message or f"Field '{rule.field_name}' must be within range {min_val} to {max_val}")
                    is_valid = False
                    
            # Enumeration validation
            elif rule_type == "enum":
                valid_values = rule.parameters.get("values", [])
                if valid_values and str(value) not in valid_values:
                    self._errors.append(rule.message or f"Field '{rule.field_name}' must be one of: {', '.join(valid_values)}")
                    is_valid = False
                    
            # Length validation
            elif rule_type == "length":
                min_len = rule.parameters.get("min")
                max_len = rule.parameters.get("max")
                if not self._check_length(value, min_len, max_len):
                    self._errors.append(rule.message or f"Field '{rule.field_name}' length must be between {min_len or 0} and {max_len or 'unlimited'}")
                    is_valid = False
                    
            # Custom validation (delegated to a registered validator)
            elif rule_type == "custom":
                validator_name = rule.parameters.get("validator")
                if validator_name and validator_name in self._validators:
                    validator = self._validators[validator_name]
                    if not validator.validate(rule.field_name, {"value": value}, context=validation_context):
                        if hasattr(validator, 'get_errors'):
                            self._errors.extend(validator.get_errors())
                        is_valid = False
                        
        return is_valid
        
    def _check_type(self, value: Any, expected_type: str) -> bool:
        """Check if value matches the expected type."""
        if expected_type == "string":
            return isinstance(value, str)
        elif expected_type == "integer":
            return isinstance(value, int)
        elif expected_type == "float" or expected_type == "number":
            return isinstance(value, (int, float))
        elif expected_type == "boolean":
            return isinstance(value, bool)
        elif expected_type == "date":
            # Basic check for ISO date format
            if not isinstance(value, str):
                return False
            try:
                import re
                return bool(re.match(r'^\d{4}-\d{2}-\d{2}$', value))
            except:
                return False
        elif expected_type == "array" or expected_type == "list":
            return isinstance(value, (list, tuple))
        elif expected_type == "object" or expected_type == "dict":
            return isinstance(value, dict)
        return True  # Unknown types considered valid
        
    def _check_pattern(self, value: Any, pattern: str) -> bool:
        """Check if value matches the pattern."""
        try:
            import re
            return bool(re.search(pattern, str(value)))
        except Exception:
            return False
            
    def _check_range(self, value: Any, min_val: Optional[float], max_val: Optional[float]) -> bool:
        """Check if numeric value is within range."""
        try:
            num_value = float(value)
            if min_val is not None and num_value < min_val:
                return False
            if max_val is not None and num_value > max_val:
                return False
            return True
        except (ValueError, TypeError):
            return False
            
    def _check_length(self, value: Any, min_len: Optional[int], max_len: Optional[int]) -> bool:
        """Check if string length is within range."""
        try:
            length = len(str(value))
            if min_len is not None and length < min_len:
                return False
            if max_len is not None and length > max_len:
                return False
            return True
        except Exception:
            return False

    def get_validation_errors(self) -> List[str]:
        """Get list of validation errors."""
        return self._errors.copy()

    def get_errors(self) -> List[str]:
        """Get validation errors (alias for get_validation_errors)."""
        return self.get_validation_errors()

    def clear_errors(self) -> None:
        """Clear validation errors."""
        self._errors.clear()

    def get_stats(self) -> Dict[str, int]:
        """Get validation statistics."""
        return self._stats.copy()