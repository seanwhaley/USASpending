"""Validation engine for handling YAML-based and core validations."""
from typing import Any, Dict, List, Optional, Set
import re
import logging
import csv
from datetime import datetime

logger = logging.getLogger(__name__)

class ValidationResult:
    """Validation result container."""
    def __init__(self, valid: bool, message: Optional[str] = None, error_type: Optional[str] = None, field_name: Optional[str] = None):
        self.valid = valid
        self.message = message
        self.error_type = error_type
        self.field_name = field_name

class ValidationEngine:
    """Handles both YAML-based and core validations."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.validation_matrix = config.get('validation_matrix', {})
        self.domain_mappings = config.get('domain_value_mapping', {})
        self.type_conversion = config.get('type_conversion', {})
        self.optional_fields = config.get('field_selection', {}).get('optional_fields', [])
        self.essential_fields = config.get('field_selection', {}).get('essential_fields', [])
        self._cache_config_values()
        self.currency_pattern = re.compile(r'[^\d.\-]')
        self.date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')

    def _cache_config_values(self) -> None:
        """Cache commonly accessed configuration values for better performance."""
        # Cache type fields for faster lookups
        self.date_fields = set(self.type_conversion.get('date_fields', []))
        self.numeric_fields = set(self.type_conversion.get('numeric_fields', []))
        self.boolean_fields = set(self.type_conversion.get('boolean_fields', []))

    def validate_field(self, field_name: str, value: Any, rules: List[Dict[str, Any]], 
                      context: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Validate a single field against its rules.
        Only performs runtime validations that cannot be expressed in YAML."""
        # Get field type first
        field_type = self._get_field_type(field_name)
        
        # Check if field is required (only for essential fields)
        is_required = field_name in self.essential_fields

        # Handle empty/null values
        if value is None or (isinstance(value, str) and not value.strip()) or str(value).strip().lower() in ('none', 'null', ''):
            if is_required:
                return ValidationResult(
                    valid=False,
                    message=f"Required field {field_name} is missing",
                    error_type=f"{field_type}_missing" if field_type else "required_field_missing",
                    field_name=field_name
                )
            return ValidationResult(True, None)

        # Convert value to string for validation
        str_value = str(value).strip()

        # Perform runtime type validation
        if field_type == 'numeric':
            try:
                cleaned = self._clean_numeric_string(str_value)
                if not cleaned:
                    return ValidationResult(True, None)
                float(cleaned)
                return ValidationResult(True, None)
            except ValueError:
                return ValidationResult(
                    valid=False,
                    message=f"Invalid numeric value for {field_name}",
                    error_type="numeric_invalid",
                    field_name=field_name
                )
        elif field_type == 'date':
            try:
                if self.date_pattern.match(str_value):
                    return ValidationResult(True, None)
                datetime.strptime(str_value[:10], '%Y-%m-%d')
                return ValidationResult(True, None)
            except ValueError:
                return ValidationResult(
                    valid=False,
                    message=f"Invalid date value for {field_name}",
                    error_type="date_invalid",
                    field_name=field_name
                )

        return ValidationResult(True, None)

    def validate_csv_columns(self, csv_path: str) -> List[ValidationResult]:
        """Validate CSV columns against configuration."""
        results = []
        try:
            encoding = self.config['global']['encoding']
            with open(csv_path, 'r', encoding=encoding) as f:
                headers = next(csv.reader(f), None)
                if not headers:
                    return [ValidationResult(
                        valid=False,
                        message="CSV file is empty",
                        error_type="empty_file"
                    )]
                
                # Only validate essential fields existence
                missing = [f for f in self.essential_fields if f not in headers]
                if missing:
                    results.append(ValidationResult(
                        valid=False,
                        message=f"CSV missing essential fields: {', '.join(missing)}",
                        error_type="missing_essential_fields",
                        field_name=",".join(missing)
                    ))
                
        except FileNotFoundError:
            results.append(ValidationResult(
                valid=False,
                message=f"CSV file not found: {csv_path}",
                error_type="file_not_found"
            ))
        except Exception as e:
            results.append(ValidationResult(
                valid=False,
                message=f"Error validating CSV structure: {str(e)}",
                error_type="validation_error"
            ))
        
        return results

    def validate_award_values(self, data: Dict[str, Any]) -> ValidationResult:
        """Validate award value relationships."""
        if ('base_exercised_options_value' in data and 
            'base_and_all_options_value' in data):
            
            try:
                exercised = float(self._clean_numeric_string(data['base_exercised_options_value']))
                total = float(self._clean_numeric_string(data['base_and_all_options_value']))
                
                if exercised > total:
                    return ValidationResult(
                        valid=False,
                        message=f"Invalid award values: base_exercised_options_value ({exercised}) > base_and_all_options_value ({total})",
                        error_type="award_value_relationship_invalid",
                        field_name="base_exercised_options_value"
                    )
            except (ValueError, TypeError):
                return ValidationResult(
                    valid=False,
                    message="Invalid numeric format for award values",
                    error_type="award_value_format_invalid",
                    field_name="base_exercised_options_value"
                )
                
        return ValidationResult(True, None)

    def _clean_numeric_string(self, value: str) -> str:
        """Clean a numeric string by removing currency symbols and commas."""
        if not isinstance(value, str):
            value = str(value)
        if not value.strip() or value.strip() in ['', 'None', 'null']:
            return ''
        cleaned = self.currency_pattern.sub('', value.strip())
        if cleaned in ['.', '-', '-.']:
            return ''
        return cleaned

    def _get_field_type(self, field_name: str) -> Optional[str]:
        """Determine the type of a field based on configuration."""
        if field_name in self.date_fields:
            return 'date'
        if field_name in self.numeric_fields:
            return 'numeric'
        if field_name in self.boolean_fields:
            return 'boolean'
        return None