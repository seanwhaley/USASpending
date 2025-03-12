from pathlib import Path
import csv
import json
from typing import Dict, Any, cast

from .fields import FieldDefinition, FieldDefinitionLoader
from .exceptions import ConfigError, FileOperationError

class FieldIO:
    """Handles field definition I/O operations."""

    @staticmethod
    def load_from_csv(csv_path: Path, config: Dict[str, Any]) -> Dict[str, Any]:
        """Load field properties from CSV file."""
        field_properties: Dict[str, Any] = config.get('field_properties', {})
        
        try:
            with open(csv_path, 'r', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    field_name = row['field_name']
                    if field_name in field_properties:
                        field_properties[field_name].update({
                            'description': row.get('description'),
                            'type': row.get('type', field_properties[field_name]['type']),
                            'required': row.get('required', '').lower() == 'true',
                            'is_key': row.get('is_key', '').lower() == 'true'
                        })
                    else:
                        field_properties[field_name] = {
                            'type': row['type'],
                            'description': row.get('description'),
                            'required': row.get('required', '').lower() == 'true',
                            'is_key': row.get('is_key', '').lower() == 'true'
                        }
            return field_properties
            
        except Exception as e:
            raise FileOperationError(f"Failed to load data dictionary CSV: {str(e)}")

    @staticmethod
    def save_to_json(fields: Dict[str, FieldDefinition], json_path: Path) -> None:
        """Save field definitions to JSON file."""
        if not fields:
            raise ValueError("Fields dictionary cannot be empty")
        if not isinstance(json_path, Path):
            raise TypeError("json_path must be a Path object")

        try:
            data = {
                'fields': {
                    name: {
                        'type': field.type,
                        'description': field.description,
                        'source_field': field.source_field,
                        'transformations': field.transformations,
                        'validation_rules': field.validation_rules,
                        'required': field.required,
                        'is_key': field.is_key,
                        'default_value': field.default_value,
                        'groups': field.groups
                    }
                    for name, field in fields.items()
                }
            }
            
            with open(json_path, 'w') as f:
                json.dump(data, f, indent=2)
        except (IOError, TypeError, json.JSONDecodeError) as e:
            raise FileOperationError(f"Failed to save field definitions to JSON: {str(e)}")