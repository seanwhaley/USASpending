"""Entity validation functionality."""
from typing import Dict, Any, List, Optional, Set, Union
import logging
from typing_extensions import TypedDict

from .interfaces import IValidator
from .config import ConfigManager
from .exceptions import ValidationError

logger = logging.getLogger(__name__)

class ValidationResult(TypedDict):
    """Result of a validation operation."""
    valid: bool
    field_name: str
    error_message: Optional[str]

class ValidationRule:
    """Represents a validation rule with configuration."""
    
    def __init__(self, field: str, rule_type: str, params: Dict[str, Any]):
        self.field = field
        self.rule_type = rule_type
        self.params = params

    @classmethod
    def from_yaml(cls, config: Dict[str, Any]) -> 'ValidationRule':
        """Create a validation rule from YAML configuration."""
        if not config.get('field'):
            raise ValidationError("Validation rule missing required 'field' parameter")
        return cls(
            field=config['field'],
            rule_type=config.get('type', 'required'),
            params=config.get('params', {})
        )

class ValidationEngine(IValidator):
    """Validates entities against configured rules."""
    
    def __init__(self, config: ConfigManager):
        """Initialize validation engine with configuration."""
        self.config = config.config
        self._load_validation_rules()
        self._initialize_dependencies()

    def _load_validation_rules(self) -> None:
        """Load validation rules from configuration."""
        self.rules: Dict[str, List[ValidationRule]] = {}
        validation_config = self.config.get('validation_types', {})
        
        for entity_type, rules in validation_config.items():
            self.rules[entity_type] = []
            for rule_config in rules:
                try:
                    rule = ValidationRule.from_yaml(rule_config)
                    self.rules[entity_type].append(rule)
                except Exception as e:
                    logger.error(f"Error loading validation rule for {entity_type}: {e}")

    def _initialize_dependencies(self) -> None:
        """Initialize field dependencies for validation ordering."""
        self.dependencies: Dict[str, Set[str]] = {}
        dependency_config = self.config.get('field_dependencies', {})
        
        for field, deps in dependency_config.items():
            self.dependencies[field] = set()
            for dep in deps:
                if isinstance(dep, str):
                    self.dependencies[field].add(dep)
                elif isinstance(dep, dict) and 'field' in dep:
                    self.dependencies[field].add(dep['field'])

    def validate_record(self, record: Dict[str, Any]) -> bool:
        """Validate a record against configured rules."""
        try:
            results = self._validate_record_with_rules(record)
            return all(result['valid'] for result in results)
        except Exception as e:
            logger.error(f"Validation error: {str(e)}")
            return False

    def _validate_record_with_rules(self, record: Dict[str, Any]) -> List[ValidationResult]:
        """Apply validation rules to a record."""
        results: List[ValidationResult] = []
        
        # Process fields in dependency order
        ordered_fields = self._get_ordered_fields(record.keys())
        
        for field in ordered_fields:
            field_rules = self.rules.get(field, [])
            for rule in field_rules:
                try:
                    valid = self._validate_field(record, rule)
                    results.append({
                        'valid': valid,
                        'field_name': field,
                        'error_message': None if valid else self._get_error_message(rule, record.get(field))
                    })
                except Exception as e:
                    logger.error(f"Error validating field {field}: {str(e)}")
                    results.append({
                        'valid': False,
                        'field_name': field,
                        'error_message': str(e)
                    })
        
        return results

    def _validate_field(self, record: Dict[str, Any], rule: ValidationRule) -> bool:
        """Validate a single field according to its rule."""
        value = record.get(rule.field)
        
        # Handle required field validation
        if rule.rule_type == 'required' and not value:
            return False
            
        # Skip validation if value is None/empty and field is not required
        if value is None or value == '':
            return True
            
        validator = self._get_validator(rule.rule_type)
        if not validator:
            logger.warning(f"No validator found for rule type: {rule.rule_type}")
            return True
            
        return validator(value, rule.params)

    def _get_validator(self, rule_type: str) -> Optional[callable]:
        """Get the validator function for a rule type."""
        validators = {
            'required': lambda v, p: bool(v),
            'min_length': lambda v, p: len(str(v)) >= p.get('min', 0),
            'max_length': lambda v, p: len(str(v)) <= p.get('max', float('inf')),
            'pattern': lambda v, p: bool(p.get('regex', '').match(str(v))),
            'range': lambda v, p: p.get('min', float('-inf')) <= float(v) <= p.get('max', float('inf')),
            'enum': lambda v, p: str(v) in p.get('values', []),
        }
        return validators.get(rule_type)

    def _get_error_message(self, rule: ValidationRule, value: Any) -> str:
        """Get error message for failed validation."""
        messages = self.config.get('validation_messages', {}).get(rule.rule_type, {})
        message = messages.get('default', f"Validation failed for {rule.field}")
        
        try:
            return message.format(field=rule.field, value=value, **rule.params)
        except Exception:
            return message

    def _get_ordered_fields(self, fields: Set[str]) -> List[str]:
        """Order fields based on dependencies."""
        ordered = []
        visited = set()
        temp_visited = set()
        
        def visit(field: str) -> None:
            if field in temp_visited:
                # Circular dependency detected - break the cycle
                return
            if field in visited:
                return
                
            temp_visited.add(field)
            
            for dep in self.dependencies.get(field, set()):
                if dep in fields:  # Only process dependencies that exist in the record
                    visit(dep)
                    
            temp_visited.remove(field)
            visited.add(field)
            ordered.append(field)
        
        for field in fields:
            if field not in visited:
                visit(field)
                
        return ordered