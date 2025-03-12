"""Core field handling functionality."""
from typing import Dict, Any, List, Optional, Set, cast, Literal
from dataclasses import dataclass, field
from enum import Enum, auto
from decimal import Decimal, InvalidOperation
from re import match

from .exceptions import DependencyError
from .validation import BaseValidator
from .types import FieldType, ValidationRule


@dataclass
class FieldDefinition:
    """Field definition with validation and transformation rules."""
    name: str
    type: FieldType
    description: str = ""
    source_field: Optional[str] = None
    transformations: List[Dict[str, Any]] = field(default_factory=list)
    required: bool = False
    is_key: bool = False
    default_value: Any = None
    groups: List[str] = field(default_factory=list)
    validation_rules: List[ValidationRule] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    pattern: Optional[str] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None


class FieldDefinitionLoader:
    """Creates field definitions from configuration."""

    _type_mapping = {
        # Standard types
        'STRING': FieldType.STRING,
        'INTEGER': FieldType.INTEGER,
        'FLOAT': FieldType.FLOAT,
        'BOOLEAN': FieldType.BOOLEAN,
        'DATE': FieldType.DATE,
        'MONEY': FieldType.MONEY,
        'ENUM': FieldType.ENUM,
        'LIST': FieldType.LIST,
        'COMPOSITE': FieldType.COMPOSITE,
        # Common variants
        'DECIMAL': FieldType.FLOAT,
        'NUMBER': FieldType.FLOAT,
        'TEXT': FieldType.STRING,
        'ARRAY': FieldType.LIST,
        'OBJECT': FieldType.COMPOSITE,
        'DICT': FieldType.COMPOSITE,
        'CURRENCY': FieldType.MONEY,
        # Special handling for amount fields
        'AMOUNT': FieldType.MONEY
    }

    @staticmethod
    def create_field_definition(field_name: str, properties: Dict[str, Any]) -> FieldDefinition:
        """Create field definition from properties."""
        field_type_str = properties.get('type', 'string').upper()

        # Special handling for field names that indicate money type
        if (field_type_str not in ['MONEY', 'CURRENCY', 'AMOUNT'] and
                ('amount' in field_name.lower() or
                 'price' in field_name.lower() or
                 'cost' in field_name.lower() or
                 'value' in field_name.lower())):
            field_type = FieldType.MONEY
        else:
            # Get field type from mapping or raise error if invalid
            mapped_type = FieldDefinitionLoader._type_mapping.get(field_type_str)
            if mapped_type is None:
                raise ValueError(f"Invalid field type: {field_type_str}")
            field_type = mapped_type

        validation_rules_data = properties.get("validation_rules", [])
        validation_rules = [
            ValidationRule(
                id=f"{field_name}_{rule_data['rule_type']}",  # Generate unique ID
                field_name=field_name,
                rule_type=rule_data["rule_type"],
                parameters=rule_data.get("parameters", {}),
                message=rule_data["message"]
            )
            for rule_data in validation_rules_data
        ]

        return FieldDefinition(
            name=field_name,
            type=field_type,
            description=properties.get('description', ''),
            source_field=properties.get('source_field'),
            transformations=properties.get('transformations', []),
            required=properties.get('required', False),
            is_key=properties.get('is_key', False),
            default_value=properties.get('default_value'),
            groups=properties.get('groups', []),
            validation_rules=validation_rules,
            dependencies=properties.get("dependencies", []),
            pattern=properties.get("pattern"),
            min_value=properties.get("min_value"),
            max_value=properties.get("max_value")
        )


class FieldRegistry:
    """Registry of field definitions."""

    def __init__(self) -> None:
        self._fields: Dict[str, Dict[str, FieldDefinition]] = {}

    def register_field(self, entity_type: str, field: FieldDefinition) -> None:
        """Register a field definition."""
        if entity_type not in self._fields:
            self._fields[entity_type] = {}
        self._fields[entity_type][field.name] = field

    def get_field(self, entity_type: str, field_name: str) -> Optional[FieldDefinition]:
        """Get a field definition."""
        return self._fields.get(entity_type, {}).get(field_name)

    def get_fields(self, entity_type: str) -> Dict[str, FieldDefinition]:
        """Get all fields for an entity type."""
        return self._fields.get(entity_type, {}).copy()


class FieldSelector:
    """Handles field selection and dependencies."""

    def __init__(self, registry: FieldRegistry):
        self.registry = registry

    def select_fields(self, entity_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Select and validate fields from data."""
        result = {}
        fields = self.registry.get_fields(entity_type)

        # Gather all required field names, including dependencies
        required_fields = set()
        for name, field in fields.items():
            if field.required:
                required_fields.add(name)
                required_fields.update(self.get_dependencies(entity_type, name))

        # Check if all required fields and their dependencies are present
        missing_fields = required_fields - set(data.keys())
        if missing_fields:
            raise DependencyError(f"Missing required fields or dependencies: {', '.join(missing_fields)}")

        # Process required fields first
        for name, field in fields.items():
            if field.required:
                result[name] = data[name]

        # Process optional fields
        for name, value in data.items():
            if name in fields and not fields[name].required:
                result[name] = value

        return result

    def get_dependencies(self, entity_type: str, field_name: str) -> Set[str]:
        """Get dependencies for a field."""
        dependencies = set()
        field = self.registry.get_field(entity_type, field_name)

        if field and field.dependencies:
            dependencies.update(field.dependencies)
            # Get transitive dependencies
            for dep in field.dependencies:
                dependencies.update(self.get_dependencies(entity_type, dep))

        return dependencies


class FieldValidator(BaseValidator):
    """Field-level validation."""

    _money_pattern = r'^-?\$?\s*\d+(?:,\d{3})*(?:\.\d{2})?$'

    def __init__(self, registry: FieldRegistry):
        super().__init__()  # Initialize the base class properly
        self.registry = registry
        self._errors: List[str] = []  # Initialize errors list

    def validate_field(self, entity_type: str, field_name: str, value: Any) -> bool:
        """Validate a single field."""
        field = self.registry.get_field(entity_type, field_name)
        if not field:
            return True  # Unknown fields are considered valid

        # Required field check
        if field.required and value is None:
            self.add_error(f"Required field {field_name} is missing")
            return False

        # Skip validation for None values in optional fields
        if value is None and not field.required:
            return True

        # Type validation
        if not self._validate_type(value, field.type):
            self.add_error(f"Invalid type for field {field_name}")
            return False

        # Pattern validation
        if field.pattern and not self._validate_pattern(value, field.pattern):
            self.add_error(f"Value does not match pattern for field {field_name}")
            return False

        # Range validation
        if not self._validate_range(value, field.min_value, field.max_value):
            self.add_error(f"Value out of range for field {field_name}")
            return False

        # Rule validation
        if field.validation_rules:
            for rule in field.validation_rules:
                if not self._validate_rule(value, rule):
                    return False

        return True

    def _validate_type(self, value: Any, field_type: FieldType) -> bool:
        """Validate value type."""
        if value is None:
            return True

        try:
            return {
                FieldType.STRING: lambda x: isinstance(x, str),
                FieldType.INTEGER: lambda x: isinstance(x, int),
                FieldType.FLOAT: lambda x: isinstance(x, (int, float)),
                FieldType.BOOLEAN: lambda x: isinstance(x, bool),
                FieldType.DATE: lambda x: isinstance(x, str),  # Date stored as ISO string
                FieldType.MONEY: self._validate_money_type,  # Custom money validation
                FieldType.ENUM: lambda x: isinstance(x, str),
                FieldType.LIST: lambda x: isinstance(x, list),
                FieldType.COMPOSITE: lambda x: isinstance(x, dict)
            }.get(field_type, lambda x: True)(value)
        except Exception:
            return False

    def _validate_money_type(self, value: Any) -> bool:
        """Validate money type value."""
        if isinstance(value, (int, float)):
            return True
        if isinstance(value, str):
            # Allow common currency string formats
            if not match(self._money_pattern, value.strip()):
                return False
            try:
                # Try to convert to Decimal to ensure it's a valid number
                # Remove currency symbols and commas first
                clean_value = value.strip().replace('$', '').replace(',', '')
                Decimal(clean_value)
                return True
            except InvalidOperation:
                return False
        return False

    def _validate_pattern(self, value: str, pattern: str) -> bool:
        """Validate value against pattern."""
        import re
        try:
            return bool(re.match(pattern, str(value)))
        except Exception:
            return False

    def _validate_range(self, value: Any, min_value: Optional[float], max_value: Optional[float]) -> bool:
        """Validate numeric value range."""
        try:
            if not isinstance(value, (int, float)):
                return True
            if min_value is not None and value < min_value:
                return False
            if max_value is not None and value > max_value:
                return False
            return True
        except Exception:
            return False

    def _validate_rule(self, value: Any, rule: ValidationRule) -> bool:
        """Validate value against a rule."""
        try:
            # Handle different rule types
            if rule.rule_type == "required" and value is None:
                self.add_error(rule.message)
                return False

            if value is None:
                return True  # Skip validation for None values unless required

            if rule.rule_type == "pattern":
                if not self._validate_pattern(value, rule.parameters["pattern"]):
                    self.add_error(rule.message)
                    return False

            if rule.rule_type == "range":
                if not self._validate_range(value,
                                            rule.parameters.get("min"),
                                            rule.parameters.get("max")):
                    self.add_error(rule.message)
                    return False

            return True

        except Exception as e:
            self.add_error(f"Rule validation failed: {str(e)}")
            return False


__all__ = [
    'FieldDefinition',
    'FieldRegistry',
    'FieldSelector',
    'FieldValidator',
    'FieldDefinitionLoader'
]
