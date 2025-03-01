"""Centralized validation logic."""
from typing import Dict, Any, List, Optional, Set
import re
import logging
import csv
from datetime import datetime
from .types import ValidationRule, ValidationResult

logger = logging.getLogger(__name__)

class ValidationEngine:
    """Handles both YAML-based and core validations."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.validation_matrix = config.get('validation_matrix', {})
        self.domain_mappings = config.get('domain_value_mapping', {})
        self.type_conversion = config.get('type_conversion', {})
        self.optional_fields = config.get('field_selection', {}).get('optional_fields', [])
        self.essential_fields = config.get('field_selection', {}).get('essential_fields', [])
        
        # Enhanced initialization using validation_types from config
        self.validation_types = config.get('validation_types', {})
        self._init_validation_patterns()
        self._cache_config_values()
        
    def _init_validation_patterns(self) -> None:
        """Initialize validation patterns from config."""
        # Get validation types from config
        self.validation_types = self.config.get('validation_types', {})
        
        # Get numeric pattern from validation_types
        numeric_config = self.validation_types.get('numeric', {}).get('decimal', {})
        strip_chars = numeric_config.get("strip_characters", "$,.")
        self.currency_pattern = re.compile(f'[{re.escape(strip_chars)}]')
        
        # Get date format from validation_types
        date_config = self.validation_types.get('date', {}).get('standard', {})
        self.date_format = date_config.get('format', '%Y-%m-%d')
        
        # Generate date regex pattern from format
        date_format = self.date_format.replace('%Y', r'\d{4}').replace('%m', r'\d{2}').replace('%d', r'\d{2}')
        self.date_pattern = re.compile(f'^{date_format}$')
        
        # Initialize string patterns from config
        self.string_patterns = self.validation_types.get('string', {}).get('pattern', {})
        
        # Initialize domain validations
        self.domain_config = self.validation_types.get('domain', {})

    def _cache_config_values(self) -> None:
        """Cache commonly accessed configuration values for better performance."""
        # Cache type fields for faster lookups
        self.date_fields = set(self.type_conversion.get('date_fields', []))
        self.numeric_fields = set(self.type_conversion.get('numeric_fields', []))
        self.boolean_fields = set(self.type_conversion.get('boolean_fields', []))

    def validate_field(self, field_name: str, value: Any, rules: List[ValidationRule],
                      context: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Validate a single field against its rules."""
        # Get field type first
        field_type = self._get_field_type(field_name)

        # Check if field is required (only for essential fields)
        is_required = field_name in self.essential_fields

        # Handle empty/null values
        if self._is_empty_value(value):
            return self._validate_missing_required_field(field_name, field_type, is_required)

        # Convert value to string for validation
        str_value = str(value).strip()

        # Perform runtime type validation
        if field_type == 'numeric':
            return self._validate_numeric_field(field_name, str_value, rules)
        elif field_type == 'date':
            return self._validate_date_field(field_name, str_value, rules)

        # Apply rule-based validation for other types
        return self._apply_general_rule_based_validation(field_name, str_value, rules)

    def _validate_missing_required_field(self, field_name: str, field_type: Optional[str], is_required: bool) -> ValidationResult:
        """Validates if a required field is missing."""
        if is_required:
            # Get error message and type from config
            missing_required_field_config = self.config.get('validation', {}).get('errors', {}).get('missing_required_field', {})
            message_template = missing_required_field_config.get('message', "Required field {field} is missing")
            error_type_template = missing_required_field_config.get('error_type', "{type}_missing")
            
            return ValidationResult(
                valid=False,
                message=message_template.format(field=field_name),
                error_type=error_type_template.format(type=field_type if field_type else "required_field"),
                field_name=field_name
            )
        return ValidationResult(True, None)

    def _validate_numeric_field(self, field_name: str, str_value: str, rules: List[ValidationRule]) -> ValidationResult:
        """Validates a numeric field."""
        try:
            cleaned = self._clean_numeric_string(str_value)
            if not cleaned:
                return ValidationResult(True, None)
            float(cleaned)
            # Apply rule-based validation
            for rule in rules:
                if not self._apply_rule_based_validation(rule, cleaned):
                    # Get error message from config or use default
                    error_config = self.config.get('validation', {}).get('errors', {}).get('numeric', {})
                    message_template = error_config.get('rule_violation', "Invalid numeric value for {field} based on rule {rule}")
                    
                    return ValidationResult(
                        valid=False,
                        message=message_template.format(field=field_name, rule=rule.type),
                        error_type="numeric_invalid",
                        field_name=field_name
                    )
            return ValidationResult(True, None)
        except ValueError:
            # Get error message from config or use default
            error_config = self.config.get('validation', {}).get('errors', {}).get('numeric', {})
            message_template = error_config.get('invalid', "Invalid numeric value for {field}")
            
            return ValidationResult(
                valid=False,
                message=message_template.format(field=field_name),
                error_type="numeric_invalid",
                field_name=field_name
            )

    def _validate_date_field(self, field_name: str, str_value: str, rules: List[ValidationRule]) -> ValidationResult:
        """Validates a date field."""
        try:
            # Get date format from config or use default
            date_format = self.config.get('validation_types', {}).get('date', {}).get('standard', {}).get('format', '%Y-%m-%d')
            
            if self.date_pattern.match(str_value):
                return ValidationResult(True, None)
            datetime.strptime(str_value[:10], date_format)
            # Apply rule-based validation
            for rule in rules:
                if not self._apply_rule_based_validation(rule, str_value):
                    # Get error message from config or use default
                    error_config = self.config.get('validation', {}).get('errors', {}).get('date', {})
                    message_template = error_config.get('rule_violation', "Invalid date value for {field} based on rule {rule}")
                    
                    return ValidationResult(
                        valid=False,
                        message=message_template.format(field=field_name, rule=rule.type),
                        error_type="date_invalid",
                        field_name=field_name
                    )
            return ValidationResult(True, None)
        except ValueError:
            # Get error message from config or use default
            error_config = self.config.get('validation', {}).get('errors', {}).get('date', {})
            message_template = error_config.get('invalid', "Invalid date value for {field}")
            
            return ValidationResult(
                valid=False,
                message=message_template.format(field=field_name),
                error_type="date_invalid",
                field_name=field_name
            )

    def _apply_general_rule_based_validation(self, field_name: str, str_value: str, rules: List[ValidationRule]) -> ValidationResult:
        """Applies rule-based validation for general field types."""
        for rule in rules:
            if not self._apply_rule_based_validation(rule, str_value):
                # Get error message from config or use default
                error_config = self.config.get('validation', {}).get('errors', {}).get('general', {})
                message_template = error_config.get('rule_violation', "Validation failed for {field} based on rule {rule}")
                
                return ValidationResult(
                    valid=False,
                    message=message_template.format(field=field_name, rule=rule.type),
                    error_type="invalid_value",
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
                    # Get error message from config or use default
                    error_config = self.config.get('validation', {}).get('errors', {}).get('csv', {})
                    message = error_config.get('empty_file', "CSV file is empty")
                    
                    return [ValidationResult(
                        valid=False,
                        message=message,
                        error_type="empty_file"
                    )]
                
                # Only validate essential fields existence
                missing = [f for f in self.essential_fields if f not in headers]
                if missing:
                    # Get error message from config or use default
                    error_config = self.config.get('validation', {}).get('errors', {}).get('csv', {})
                    message_template = error_config.get('missing_fields', "CSV missing essential fields: {fields}")
                    
                    results.append(ValidationResult(
                        valid=False,
                        message=message_template.format(fields=', '.join(missing)),
                        error_type="missing_essential_fields",
                        field_name=",".join(missing)
                    ))
                
        except FileNotFoundError:
            # Get error message from config or use default
            error_config = self.config.get('validation', {}).get('errors', {}).get('csv', {})
            message_template = error_config.get('file_not_found', "CSV file not found: {path}")
            
            results.append(ValidationResult(
                valid=False,
                message=message_template.format(path=csv_path),
                error_type="file_not_found"
            ))
        except Exception as e:
            # Get error message from config or use default
            error_config = self.config.get('validation', {}).get('errors', {}).get('csv', {})
            message_template = error_config.get('validation_error', "Error validating CSV structure: {error}")
            
            results.append(ValidationResult(
                valid=False,
                message=message_template.format(error=str(e)),
                error_type="validation_error"
            ))
        
        return results

    def validate_award_values(self, data: Dict[str, Any]) -> ValidationResult:
        """Validate award value relationships."""
        entity_type = data.get('type')  # Assuming 'type' field exists in data
        entity_config = (self.config.get('contracts', {})
                        .get('entity_separation', {})
                        .get('entities', {})
                        .get(entity_type, {}))

        if not entity_config or 'relationships' not in entity_config:
            return ValidationResult(True, None)

        relationships = entity_config['relationships']

        # Process value comparison relationships
        if 'value_comparison' in relationships:
            value_comparisons = relationships['value_comparison']
            for comparison_config in value_comparisons:
                field1_name = comparison_config.get('field1')
                field2_name = comparison_config.get('field2')
                relationship_type = comparison_config.get('relationship_type')
                message = comparison_config.get('message')
                error_type = comparison_config.get('error_type')

                if field1_name and field2_name and relationship_type:
                    field1_value = data.get(field1_name)
                    field2_value = data.get(field2_name)

                    if field1_value is not None and field2_value is not None:
                        try:
                            field1_num = float(self._clean_numeric_string(field1_value))
                            field2_num = float(self._clean_numeric_string(field2_value))

                            if relationship_type == 'greater_than_or_equal':
                                if not field1_num >= field2_num:
                                    return ValidationResult(
                                        valid=False,
                                        message=message or f"Invalid relationship: {field1_name} !>= {field2_name}",
                                        error_type=error_type or "relationship_invalid",
                                        field_name=field1_name
                                    )
                            elif relationship_type == 'less_than_or_equal':
                                if not field1_num <= field2_num:
                                    return ValidationResult(
                                        valid=False,
                                        message=message or f"Invalid relationship: {field1_name} !<= {field2_name}",
                                        error_type=error_type or "relationship_invalid",
                                        field_name=field1_name
                                    )
                            elif relationship_type == 'equal_to':
                                if not field1_num == field2_num:
                                    return ValidationResult(
                                        valid=False,
                                        message=message or f"Invalid relationship: {field1_name} != {field2_name}",
                                        error_type=error_type or "relationship_invalid",
                                        field_name=field1_name
                                    )
                            elif relationship_type == 'greater_than':
                                if not field1_num > field2_num:
                                    return ValidationResult(
                                        valid=False,
                                        message=message or f"Invalid relationship: {field1_name} !> {field2_name}",
                                        error_type=error_type or "relationship_invalid",
                                        field_name=field1_name
                                    )
                            elif relationship_type == 'less_than':
                                if not field1_num < field2_num:
                                    return ValidationResult(
                                        valid=False,
                                        message=message or f"Invalid relationship: {field1_name} !< {field2_name}",
                                        error_type=error_type or "relationship_invalid",
                                        field_name=field1_name
                                    )
                            # Add other relationship types here (not_equal_to, etc.)

                        except (ValueError, TypeError):
                            return ValidationResult(
                                valid=False,
                                message="Invalid numeric format for relationship values",
                                error_type="relationship_format_invalid",
                                field_name=field1_name
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
        # Load field types from config
        field_types = self.config.get('field_types', {})
        if (field_type := field_types.get(field_name)):
            return field_type
        
        if field_name in self.date_fields:
            return 'date'
        if field_name in self.numeric_fields:
            return 'numeric'
        if field_name in self.boolean_fields:
            return 'boolean'
        return None

    def _apply_rule_based_validation(self, rule: ValidationRule, value: Any) -> bool:
        """Apply rule-based validation based on ValidationRule."""
        for validation_rule in rule.rules:
            rule_type = validation_rule.get('type')
            if not self._apply_validation_rule(rule_type, value, validation_rule):
                logger.debug(f"{rule_type} validation failed for {rule.field}: {value}")
                return False
        return True

    def _apply_validation_rule(self, rule_type: str, value: Any, rule_config: Dict[str, Any]) -> bool:
        """Apply a specific validation rule."""
        validators = {
            'pattern': self._validate_pattern,
            'range': self._validate_range,
            'enum': self._validate_enum,
            'reference': self._validate_reference,
            'decimal': self._validate_decimal,  # Add decimal validation
            'date': self._validate_date  # Add date validation
        }

        validator = validators.get(rule_type)
        return validator(value, rule_config) if validator else True

    def _validate_pattern(self, value: Any, rule_config: Dict[str, Any]) -> bool:
        pattern = rule_config.get('pattern', '')
        return bool(re.match(pattern, str(value)))

    def _validate_range(self, value: Any, rule_config: Dict[str, Any]) -> bool:
        try:
            num_value = float(value)
            min_val = rule_config.get('min')
            max_val = rule_config.get('max')
            return ((min_val is None or num_value >= min_val) and 
                   (max_val is None or num_value <= max_val))
        except (TypeError, ValueError):
            return False

    def _validate_enum(self, value: Any, rule_config: Dict[str, Any]) -> bool:
        return str(value) in rule_config.get('values', [])

    def _validate_reference(self, value: Any, rule_config: Dict[str, Any]) -> bool:
        """Validate a reference to another entity."""
        target_store = rule_config.get('target_store')
        if target_store and hasattr(self, target_store):
            # Assuming the target store has a cache attribute
            return value in getattr(self, target_store).cache
        return False

    def _validate_decimal(self, value: Any, rule_config: Dict[str, Any]) -> bool:
        """Validate a decimal value."""
        try:
            float_val = float(str(value).strip('$,'))
            if 'min_value' in rule_config:
                return float_val >= rule_config['min_value']
            if 'max_value' in rule_config:
                return float_val <= rule_config['max_value']
            return True
        except (ValueError, TypeError):
            return False

    def _validate_date(self, value: Any, rule_config: Dict[str, Any]) -> bool:
        """Validate a date value."""
        try:
            datetime.strptime(str(value), rule_config.get('format', '%Y-%m-%d'))
            return True
        except (ValueError, TypeError):
            return False

    def _validate_field_by_type(self, field_name: str, value: Any, field_type: str) -> ValidationResult:
        """Validate a field based on its type configuration."""
        type_config = self.validation_types.get(field_type, {})
        
        if not type_config:
            return ValidationResult(True, None)
            
        if field_type == 'numeric':
            return self._validate_numeric_with_config(field_name, value, type_config)
        elif field_type == 'date':
            return self._validate_date_with_config(field_name, value, type_config)
        elif field_type == 'string':
            return self._validate_string_with_config(field_name, value, type_config)
        elif field_type == 'domain':
            return self._validate_domain_with_config(field_name, value, type_config)
            
        return ValidationResult(True, None)

    def _validate_numeric_with_config(self, field_name: str, value: str, config: Dict[str, Any]) -> ValidationResult:
        """Validate numeric fields using type configuration."""
        try:
            cleaned = self._clean_numeric_string(value)
            if not cleaned:
                return ValidationResult(True, None)
                
            num_value = float(cleaned)
            
            # Apply numeric validations from config
            for rule_type, rule_config in config.items():
                if rule_type == 'decimal':
                    if 'precision' in rule_config:
                        decimal_places = len(cleaned.split('.')[-1]) if '.' in cleaned else 0
                        if decimal_places > rule_config['precision']:
                            return ValidationResult(
                                valid=False,
                                message=f"Value exceeds maximum precision of {rule_config['precision']} for {field_name}",
                                error_type="precision_exceeded",
                                field_name=field_name
                            )
                
                if 'min_value' in rule_config and num_value < rule_config['min_value']:
                    return ValidationResult(
                        valid=False,
                        message=f"Value below minimum {rule_config['min_value']} for {field_name}",
                        error_type="below_minimum",
                        field_name=field_name
                    )
                
                if 'max_value' in rule_config and num_value > rule_config['max_value']:
                    return ValidationResult(
                        valid=False,
                        message=f"Value above maximum {rule_config['max_value']} for {field_name}",
                        error_type="above_maximum",
                        field_name=field_name
                    )
            
            return ValidationResult(True, None)
            
        except ValueError:
            return ValidationResult(
                valid=False,
                message=f"Invalid numeric value for {field_name}",
                error_type="numeric_invalid",
                field_name=field_name
            )

    def _validate_date_with_config(self, field_name: str, value: Any, config: Dict[str, Any]) -> ValidationResult:
        """Validate date fields using type configuration."""
        try:
            # Get format from config
            date_format = config.get('format', self.date_format)
            
            if not value or str(value).strip() in self.config.get('validation', {}).get('empty_values', ['', 'None', 'null']):
                return ValidationResult(True, None)
                
            datetime.strptime(str(value), date_format)
            
            # Apply other date validations from config
            if config.get('not_future', False) and datetime.strptime(str(value), date_format) > datetime.now():
                error_config = self.config.get('validation', {}).get('errors', {}).get('date', {})
                message = error_config.get('future_date', f"Future date not allowed for {field_name}")
                return ValidationResult(valid=False, message=message, error_type="future_date", field_name=field_name)
                
            return ValidationResult(True, None)
        except ValueError:
            error_config = self.config.get('validation', {}).get('errors', {}).get('date', {})
            message = error_config.get('invalid', f"Invalid date format for {field_name}")
            return ValidationResult(valid=False, message=message, error_type="date_invalid", field_name=field_name)

    def _is_empty_value(self, value: Any) -> bool:
        """Check if a value is considered empty based on configuration."""
        empty_values = self.config.get('validation', {}).get('empty_values', ['', 'None', 'null', 'na', 'n/a'])
        return (value is None or 
                (isinstance(value, str) and not value.strip()) or 
                str(value).strip().lower() in [v.lower() for v in empty_values])

    def validate_field_mapping(self, field_name: str, value: Any, mappings: List[Dict[str, Any]]) -> ValidationResult:
        """Validate a field against its mappings."""
        # Skip validation if no mappings defined
        if not mappings:
            return ValidationResult(True, None)

        for mapping in mappings:
            if mapping.get('source') == field_name:
                # Get target field
                target = mapping.get('target')
                if not target:
                    return ValidationResult(
                        valid=False,
                        message=f"Missing target field in mapping for {field_name}",
                        error_type="mapping_invalid",
                        field_name=field_name
                    )

                # Validate nested field structure
                if '.' in target:
                    parent, child = target.split('.', 1)
                    if not self._validate_nested_field(parent, child):
                        return ValidationResult(
                            valid=False,
                            message=f"Invalid nested field mapping {target} for {field_name}",
                            error_type="mapping_invalid",
                            field_name=field_name
                        )

                # Get validation rules for target field
                target_rules = self.validation_matrix.get(target, [])
                if target_rules:
                    result = self.validate_field(target, value, target_rules)
                    if not result.valid:
                        return result

        return ValidationResult(True, None)

    def _validate_nested_field(self, parent: str, child: str) -> bool:
        """Validate a nested field structure."""
        # Get parent configuration
        parent_config = self.config.get('field_structure', {}).get(parent, {})
        if not parent_config:
            return False

        # Check if child field is allowed in parent
        allowed_children = parent_config.get('allowed_fields', [])
        return child in allowed_children or '*' in allowed_children

    def validate_entity_config(self, entity_name: str, entity_config: Dict[str, Any]) -> ValidationResult:
        """Validate an entity configuration section."""
        if not isinstance(entity_config, dict):
            return ValidationResult(
                valid=False,
                message=f"Entity configuration for {entity_name} must be a dictionary",
                error_type="config_invalid",
                field_name=entity_name
            )

        # Check required fields
        required_fields = ['entity_type', 'entity_processing']
        missing = [f for f in required_fields if f not in entity_config]
        if missing:
            return ValidationResult(
                valid=False,
                message=f"Missing required fields in {entity_name} config: {', '.join(missing)}",
                error_type="config_missing_fields",
                field_name=entity_name
            )

        # Check processing configuration
        proc_config = entity_config.get('entity_processing', {})
        if not proc_config.get('store_type'):
            return ValidationResult(
                valid=False,
                message=f"Missing store_type in {entity_name} processing config",
                error_type="config_missing_store_type",
                field_name=entity_name
            )

        return ValidationResult(True, None)

    def validate_processing_order(self, entity_configs: Dict[str, Dict[str, Any]]) -> List[ValidationResult]:
        """Validate entity processing order configuration."""
        results = []
        
        # Check for circular dependencies
        dependencies = {}
        for entity_name, config in entity_configs.items():
            deps = []
            if 'relationships' in config:
                for rel in config['relationships']:
                    if 'depends_on' in rel:
                        deps.append(rel['depends_on'])
            dependencies[entity_name] = deps

        # Check for cycles
        visited = set()
        temp_visited = set()

        def has_cycle(node: str) -> bool:
            if node in temp_visited:
                return True
            if node in visited:
                return False
            temp_visited.add(node)
            for dep in dependencies.get(node, []):
                if has_cycle(dep):
                    return True
            temp_visited.remove(node)
            visited.add(node)
            return False

        for entity in dependencies:
            if has_cycle(entity):
                results.append(ValidationResult(
                    valid=False,
                    message=f"Circular dependency detected involving {entity}",
                    error_type="circular_dependency",
                    field_name=entity
                ))

        # Validate processing order values
        seen_orders = set()
        for entity_name, config in entity_configs.items():
            order = config.get('entity_processing', {}).get('processing_order')
            if order is None:
                results.append(ValidationResult(
                    valid=False,
                    message=f"Missing processing_order for {entity_name}",
                    error_type="missing_processing_order",
                    field_name=entity_name
                ))
            elif order in seen_orders:
                results.append(ValidationResult(
                    valid=False,
                    message=f"Duplicate processing order {order} for {entity_name}",
                    error_type="duplicate_processing_order",
                    field_name=entity_name
                ))
            seen_orders.add(order)

        return results

    def validate_csv_structure(self, headers: List[str]) -> ValidationResult:
        """Validate CSV structure against configuration."""
        if not headers:
            return ValidationResult(
                valid=False,
                message="CSV file has no headers",
                error_type="no_headers"
            )

        # Get required fields from config
        required_fields = set(self.essential_fields)
        
        # Check for missing required fields
        missing = required_fields - set(headers)
        if missing:
            return ValidationResult(
                valid=False,
                message=f"Missing required fields in CSV: {', '.join(missing)}",
                error_type="missing_required_fields",
                field_name=",".join(missing)
            )

        # Validate field patterns if configured
        field_patterns = self.config.get('field_validation', {}).get('patterns', {})
        for field in headers:
            for pattern_name, pattern in field_patterns.items():
                if pattern.get('required', False) and not any(re.match(p, field) for p in pattern.get('matches', [])):
                    return ValidationResult(
                        valid=False,
                        message=f"Field {field} does not match required pattern {pattern_name}",
                        error_type="invalid_field_pattern",
                        field_name=field
                    )

        return ValidationResult(True, None)

    def validate_chunk_config(self, config: Dict[str, Any]) -> ValidationResult:
        """Validate chunking configuration."""
        # Check contracts section
        if 'contracts' not in config:
            return ValidationResult(
                valid=False,
                message="Missing contracts configuration section",
                error_type="config_missing_section",
                field_name="contracts"
            )

        chunk_config = config['contracts'].get('chunking', {})
        if not chunk_config.get('enabled', False):
            return ValidationResult(
                valid=False,
                message="Chunking must be enabled",
                error_type="chunking_disabled",
                field_name="contracts.chunking.enabled"
            )

        if 'records_per_chunk' not in chunk_config:
            return ValidationResult(
                valid=False,
                message="records_per_chunk required in chunking config",
                error_type="missing_chunk_size",
                field_name="contracts.chunking.records_per_chunk"
            )

        return ValidationResult(True, None)

    def validate_field_mappings(self, field_mappings: Dict[str, Any]) -> ValidationResult:
        """Validate field mappings configuration."""
        if not isinstance(field_mappings, dict):
            return ValidationResult(
                valid=False,
                message="Field mappings must be a dictionary",
                error_type="invalid_mapping_type"
            )

        for source, mapping in field_mappings.items():
            # Check direct string mappings
            if isinstance(mapping, str):
                continue
            
            # Check list mappings
            if isinstance(mapping, list):
                if not all(isinstance(m, str) for m in mapping):
                    return ValidationResult(
                        valid=False,
                        message=f"All field mappings for {source} must be strings",
                        error_type="invalid_mapping_value",
                        field_name=source
                    )
                continue
            
            # Check dictionary mappings
            if isinstance(mapping, dict):
                required_fields = ['target']
                missing = [f for f in required_fields if f not in mapping]
                if missing:
                    return ValidationResult(
                        valid=False,
                        message=f"Missing required fields in mapping for {source}: {', '.join(missing)}",
                        error_type="missing_mapping_fields",
                        field_name=source
                    )
                continue
                
            return ValidationResult(
                valid=False,
                message=f"Invalid mapping type for {source}",
                error_type="invalid_mapping_type",
                field_name=source
            )
        
        return ValidationResult(True, None)

    def validate_clean_record(self, record: Dict[str, Any], keep_fields: Set[str], excluded_patterns: Set[str]) -> Dict[str, Any]:
        """Validate and clean a record for chunking.
        
        Args:
            record: Original record to clean
            keep_fields: Fields that should always be kept
            excluded_patterns: Patterns for fields that should be excluded
            
        Returns:
            Cleaned record with only valid fields
        """
        cleaned: Dict[str, Any] = {}
        
        for key, value in record.items():
            # Check if field should be kept
            if (key in keep_fields or
                not any(key.startswith(pattern) for pattern in excluded_patterns) or
                key.endswith('_ref')):
                
                # Get field mappings from config
                field_mappings = self.config.get('field_transformations', {}).get('mappings', [])
                
                # Validate field mapping
                result = self.validate_field_mapping(key, value, field_mappings)
                if not result.valid:
                    if not self.config['contracts']['input'].get('skip_invalid_rows', False):
                        logger.warning(f"Field mapping validation failed: {result.message}")
                        continue

                # Apply the mapping or keep original field
                mapping_found = False
                for mapping in field_mappings:
                    if mapping.get('source') == key:
                        target = mapping.get('target')
                        if target:
                            if '.' in target:
                                parent, child = target.split('.', 1)
                                if parent not in cleaned:
                                    cleaned[parent] = {}
                                cleaned[parent][child] = value
                            else:
                                cleaned[target] = value
                            mapping_found = True
                            break
                
                if not mapping_found:
                    cleaned[key] = value
        
        return cleaned

    def validate_entity(self, entity_type: str, entity_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> List[ValidationResult]:
        """Validate entity data against rules and relationships.

        Args:
            entity_type: Type of entity being validated 
            entity_data: Entity data to validate
            context: Optional context data (full record) for relationship validation

        Returns:
            List of validation results
        """
        results = []

        # Get entity validation rules from config
        entity_config = (self.config.get('contracts', {})
                        .get('entity_separation', {})
                        .get('entities', {})
                        .get(entity_type, {}))

        validation_rules = entity_config.get('validation', {})
        
        # Validate required fields
        for field in entity_config.get('required_fields', []):
            if field not in entity_data or self._is_empty_value(entity_data[field]):
                results.append(ValidationResult(
                    valid=False,
                    message=f"Missing required field {field} for {entity_type}",
                    error_type="missing_required_field",
                    field_name=field
                ))
                
        # Validate field values
        for field, rules in validation_rules.items():
            if field in entity_data:
                result = self.validate_field(field, entity_data[field], rules, context)
                if not result.valid:
                    results.append(result)

        # Validate relationships if context provided
        if context and 'relationships' in entity_config:
            result = self.validate_award_values(entity_data)
            if not result.valid:
                results.append(result)

        return results

    def validate_record(self, record: Dict[str, Any], entity_stores: Dict[str, EntityStore]) -> List[ValidationResult]:
        """Validate a full record across all entities.
        
        Args:
            record: Record to validate
            entity_stores: Dictionary of entity stores
            
        Returns:
            List of validation results
        """
        results = []
        
        # Validate each entity type
        for entity_type, store in entity_stores.items():
            # Extract entity data without adding it
            entity_data = store.extract_entity_data(record)
            if entity_data:
                # Validate the entity data
                entity_results = self.validate_entity(entity_type, entity_data, context=record)
                results.extend(entity_results)
                
        return results