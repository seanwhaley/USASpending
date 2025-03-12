"""Data dictionary management for field mappings and transformations."""
from typing import Dict, Any, Optional, List, Set, cast
from collections import defaultdict
from pathlib import Path

from .core.fields import FieldDefinition, FieldDefinitionLoader
from .core.validation_mediator import ValidationMediator
from .core.transformers import TransformationEngine
from .core.adapters import AdapterFactory, BaseAdapter
from .core.field_io import FieldIO
from .core.types import RuleType, ValidationRule, ValidationSeverity, EntityData
from .core.validation import RuleSet
from .core.exceptions import ConfigurationError
from .core.logging_config import get_logger

logger = get_logger(__name__)

class Dictionary:
    """Manages field definitions using core components."""
    
    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize Dictionary instance."""
        self.fields: Dict[str, FieldDefinition] = {}
        self.field_groups: Dict[str, Set[str]] = defaultdict(set)
        self._validation_mediator = ValidationMediator()
        self._transform_engine = TransformationEngine()
        self._adapter_factory = AdapterFactory()
        self._adapters: Dict[str, BaseAdapter] = {}
        self._load_fields(config)
        self._setup_validation_rules()

    def _load_fields(self, config: Dict[str, Any]) -> None:
        """Load field definitions from configuration."""
        field_properties = config.get("field_properties", {})
        if not field_properties:
            logger.warning("No field properties found in config")
            return
            
        for field_name, properties in field_properties.items():
            try:
                # Create field definition using the loader
                field_def = FieldDefinitionLoader.create_field_definition(field_name, properties)
                if not field_def:
                    continue
                    
                self.fields[field_name] = field_def
                
                # Register field in appropriate groups
                for group_name in field_def.groups:
                    self.field_groups[group_name].add(field_name)
                    
                # Create appropriate adapter for the field
                if field_def.transformations:
                    self._adapters[field_name] = self._adapter_factory.create_adapter(
                        field_def.type,
                        field_def.transformations,
                        field_name=field_name
                    )
                    
            except ValueError as e:
                logger.error(f"Error loading field {field_name}: {e}")

    def _setup_validation_rules(self) -> None:
        """Set up validation rules based on field definitions."""
        for field_name, field_def in self.fields.items():
            # Convert FieldDefinition validation rules directly
            rules: List[ValidationRule] = []
            for validation_rule in field_def.validation_rules:
                try:
                    rules.append(validation_rule)
                except Exception as e:
                    logger.warning(f"Invalid validation rule for field {field_name}: {e}")
                    continue

            # Create rule set for organization but pass only the rules to register_rules
            rule_set = RuleSet(
                name=field_name,
                rules=rules,
                enabled=True
            )
            self._validation_mediator.register_rules(field_name, rules)

    def get_field(self, field_name: str) -> Optional[FieldDefinition]:
        """Get field definition by name."""
        return self.fields.get(field_name)

    def get_field_type(self, field_name: str) -> Optional[str]:
        """Get field type by name."""
        field = self.get_field(field_name)
        if field:
            return field.type.name
        return None

    def get_field_transformations(self, field_name: str) -> List[Dict[str, Any]]:
        """Get transformations for a field."""
        field = self.get_field(field_name)
        if field:
            return field.transformations
        return []

    def get_field_validation_rules(self, field_name: str) -> List[ValidationRule]:
        """Get validation rules for a field."""
        return self._validation_mediator._rule_sets.get(field_name, RuleSet(field_name, [])).rules

    def get_fields_in_group(self, group_name: str) -> List[str]:
        """Get fields belonging to a validation group."""
        return sorted(self.field_groups.get(group_name, set()))

    def get_key_fields(self) -> List[str]:
        """Get list of key fields."""
        return [
            name for name, field in self.fields.items()
            if field.is_key
        ]

    def get_required_fields(self) -> List[str]:
        """Get list of required fields."""
        return [
            name for name, field in self.fields.items()
            if field.required
        ]

    def validate_field(self, field_name: str, value: Any) -> List[str]:
        """Validate a field value."""
        data = {field_name: value}
        
        # Use field_name directly as rule set name to match registration
        if not self._validation_mediator.validate_entity(field_name, data, {"rule_set": field_name}):
            return self._validation_mediator.get_validation_errors()
        return []

    def transform_field(self, field_name: str, value: Any) -> Any:
        """Transform a field value."""
        adapter = self._adapters.get(field_name)
        if not adapter:
            return value
            
        try:
            return adapter.transform_field(value)
        except Exception as e:
            logger.error(f"Transform failed for {field_name}: {str(e)}")
            return None

    @classmethod
    def from_csv(cls, csv_path: Path, config: Dict[str, Any]) -> "Dictionary":
        """Create Dictionary instance from CSV file."""
        field_properties = FieldIO.load_from_csv(csv_path, config)
        config["field_properties"] = field_properties
        return cls(config)

    def to_json(self, json_path: Path) -> None:
        """Save dictionary to JSON file."""
        FieldIO.save_to_json(self.fields, json_path)

    def cleanup(self) -> None:
        """Clean up resources."""
        self._adapters.clear()
        self.fields.clear()
        self.field_groups.clear()