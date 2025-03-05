"""Data dictionary management for field mappings and transformations."""
from typing import Dict, Any, Optional, List, Set
from pathlib import Path
import csv
import json
from dataclasses import dataclass, field
from collections import defaultdict

from .exceptions import ConfigurationError
from .logging_config import get_logger
from .schema_mapping import SchemaMapping
from .transformers import TransformerFactory
from .interfaces import ISchemaAdapter

logger = get_logger(__name__)

@dataclass
class FieldDefinition:
    """Field definition in data dictionary.

    Attributes:
        name: Field name
        type: Field data type
        description: Optional field description
        source_field: Optional source field name for mapping
        transformations: List of transformation operations
        validation_rules: List of validation rules
        is_required: Whether field is required
        is_key: Whether field is a key field
        default_value: Default value if field is missing
        groups: List of validation groups field belongs to
    """
    name: str
    type: str
    description: Optional[str] = None
    source_field: Optional[str] = None
    transformations: List[Dict[str, Any]] = field(default_factory=list)
    validation_rules: List[Dict[str, Any]] = field(default_factory=list)
    is_required: bool = False
    is_key: bool = False
    default_value: Any = None
    groups: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Validate field definition after initialization."""
        if not self.name:
            raise ValueError("Field name is required")
        if not self.type:
            raise ValueError("Field type is required")
        
        # Set source field to name if not specified
        if not self.source_field:
            self.source_field = self.name

    def has_transformation(self, transform_type: str) -> bool:
        """Check if field has a specific transformation type.
        
        Args:
            transform_type: Type of transformation to check for
            
        Returns:
            True if transformation exists, False otherwise
        """
        return any(t.get('type') == transform_type for t in self.transformations)

    def has_validation_rule(self, rule_type: str) -> bool:
        """Check if field has a specific validation rule.
        
        Args:
            rule_type: Type of validation rule to check for
            
        Returns:
            True if rule exists, False otherwise
        """
        return any(r.get('type') == rule_type for r in self.validation_rules)

    def in_group(self, group_name: str) -> bool:
        """Check if field belongs to a validation group.
        
        Args:
            group_name: Name of group to check
            
        Returns:
            True if field is in group, False otherwise
        """
        return group_name in self.groups

    def to_dict(self) -> Dict[str, Any]:
        """Convert field definition to dictionary.
        
        Returns:
            Dictionary representation of field definition
        """
        return {
            'name': self.name,
            'type': self.type,
            'description': self.description,
            'source_field': self.source_field,
            'transformations': self.transformations,
            'validation_rules': self.validation_rules,
            'is_required': self.is_required,
            'is_key': self.is_key,
            'default_value': self.default_value,
            'groups': self.groups
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FieldDefinition':
        """Create field definition from dictionary.
        
        Args:
            data: Dictionary containing field definition
            
        Returns:
            New FieldDefinition instance
        """
        return cls(
            name=data['name'],
            type=data['type'],
            description=data.get('description'),
            source_field=data.get('source_field'),
            transformations=data.get('transformations', []),
            validation_rules=data.get('validation_rules', []),
            is_required=data.get('is_required', False),
            is_key=data.get('is_key', False),
            default_value=data.get('default_value'),
            groups=data.get('groups', [])
        )

class Dictionary:
    """Manages field definitions and transformations."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize dictionary with configuration.
        
        Args:
            config: Configuration dictionary with field definitions
        """
        self.fields: Dict[str, FieldDefinition] = {}
        self.field_groups: Dict[str, Set[str]] = defaultdict(set)
        self.adapters: Dict[str, ISchemaAdapter] = {}
        self._transformer_factory = TransformerFactory()
        self._schema_mapping = SchemaMapping(self._transformer_factory)
        self._load_fields(config)
        self._initialize_adapters()

    def _load_fields(self, config: Dict[str, Any]) -> None:
        """Load field definitions from configuration.
        
        Args:
            config: Configuration dictionary
        """
        field_properties = config.get('field_properties', {})
        
        for field_name, props in field_properties.items():
            validation = props.get('validation', {})
            field_def = FieldDefinition(
                name=field_name,
                type=props['type'],
                description=props.get('description'),
                source_field=props.get('source_field'),
                transformations=props.get('transformation', {}).get('operations', []),
                validation_rules=validation.get('rules', []),
                is_required=props.get('required', False),
                is_key=props.get('is_key', False),
                default_value=props.get('default'),
                groups=validation.get('groups', [])
            )
            self.fields[field_name] = field_def
            
            # Update field group mappings
            for group in field_def.groups:
                self.field_groups[group].add(field_name)

    def _initialize_adapters(self) -> None:
        """Initialize schema adapters for fields."""
        for field_name, field_def in self.fields.items():
            try:
                adapter = self._schema_mapping.create_adapter(
                    field_def.type,
                    {
                        'validation': {
                            'rules': field_def.validation_rules,
                            'groups': field_def.groups
                        },
                        'transformation': {
                            'operations': field_def.transformations
                        }
                    }
                )
                if adapter:
                    self.adapters[field_name] = adapter
            except Exception as e:
                logger.error(f"Failed to create adapter for {field_name}: {str(e)}")

    def get_field(self, field_name: str) -> Optional[FieldDefinition]:
        """Get field definition by name.
        
        Args:
            field_name: Name of the field
            
        Returns:
            FieldDefinition if found, None otherwise
        """
        return self.fields.get(field_name)

    def get_field_type(self, field_name: str) -> Optional[str]:
        """Get field type by name.
        
        Args:
            field_name: Name of the field
            
        Returns:
            Field type if found, None otherwise
        """
        field = self.get_field(field_name)
        return field.type if field else None

    def get_field_transformations(self, field_name: str) -> List[Dict[str, Any]]:
        """Get transformations for a field.
        
        Args:
            field_name: Name of the field
            
        Returns:
            List of transformation configurations
        """
        field = self.get_field(field_name)
        return field.transformations if field else []

    def get_validation_rules(self, field_name: str) -> List[Dict[str, Any]]:
        """Get validation rules for a field.
        
        Args:
            field_name: Name of the field
            
        Returns:
            List of validation rules
        """
        field = self.get_field(field_name)
        return field.validation_rules if field else []

    def get_fields_by_group(self, group_name: str) -> List[str]:
        """Get fields belonging to a validation group.
        
        Args:
            group_name: Name of the validation group
            
        Returns:
            List of field names in the group
        """
        return sorted(self.field_groups.get(group_name, set()))

    def get_key_fields(self) -> List[str]:
        """Get list of key fields.
        
        Returns:
            List of field names that are marked as keys
        """
        return [name for name, field in self.fields.items() if field.is_key]

    def get_required_fields(self) -> List[str]:
        """Get list of required fields.
        
        Returns:
            List of field names that are marked as required
        """
        return [name for name, field in self.fields.items() if field.is_required]

    def validate_field(self, field_name: str, value: Any) -> List[str]:
        """Validate a field value.
        
        Args:
            field_name: Name of the field to validate
            value: Value to validate
            
        Returns:
            List of validation error messages
        """
        adapter = self.adapters.get(field_name)
        if not adapter:
            return []
            
        if not adapter.validate(value, field_name):
            return adapter.get_validation_errors()
        return []

    def transform_field(self, field_name: str, value: Any) -> Any:
        """Transform a field value.
        
        Args:
            field_name: Name of the field to transform
            value: Value to transform
            
        Returns:
            Transformed value
        """
        adapter = self.adapters.get(field_name)
        if not adapter:
            return value
            
        try:
            return adapter.transform(value, field_name)
        except Exception as e:
            logger.error(f"Transform failed for {field_name}: {str(e)}")
            return None

    @classmethod
    def from_csv(cls, csv_path: Path, config: Dict[str, Any]) -> 'Dictionary':
        """Create dictionary from CSV file and base config.
        
        Args:
            csv_path: Path to CSV data dictionary file
            config: Base configuration to extend
            
        Returns:
            New Dictionary instance
            
        Raises:
            ConfigurationError: If CSV file cannot be loaded
        """
        try:
            field_properties = config.get('field_properties', {})
            
            with open(csv_path, 'r', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    field_name = row['field_name']
                    if field_name in field_properties:
                        # Update existing field definition
                        field_properties[field_name].update({
                            'description': row.get('description'),
                            'type': row.get('type', field_properties[field_name]['type']),
                            'required': row.get('required', '').lower() == 'true',
                            'is_key': row.get('is_key', '').lower() == 'true'
                        })
                    else:
                        # Add new field definition
                        field_properties[field_name] = {
                            'type': row['type'],
                            'description': row.get('description'),
                            'required': row.get('required', '').lower() == 'true',
                            'is_key': row.get('is_key', '').lower() == 'true'
                        }
            
            config['field_properties'] = field_properties
            return cls(config)
            
        except Exception as e:
            raise ConfigurationError(f"Failed to load data dictionary CSV: {str(e)}")

    def to_json(self, json_path: Path) -> None:
        """Save dictionary to JSON file.
        
        Args:
            json_path: Path to save JSON file
        """
        data = {
            'fields': {
                name: {
                    'type': field.type,
                    'description': field.description,
                    'source_field': field.source_field,
                    'transformations': field.transformations,
                    'validation_rules': field.validation_rules,
                    'is_required': field.is_required,
                    'is_key': field.is_key,
                    'default_value': field.default_value,
                    'groups': field.groups
                }
                for name, field in self.fields.items()
            }
        }
        
        with open(json_path, 'w') as f:
            json.dump(data, f, indent=2)