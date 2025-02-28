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
        self.validation_rules = config.get('type_conversion', {}).get('value_validation', {})
        self._compile_patterns()
        self.date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')
        self.optional_fields = config.get('field_selection', {}).get('optional_fields', [])
        self.essential_fields = config.get('field_selection', {}).get('essential_fields', [])
        # Cache frequently accessed config values
        self._cache_config_values()
        self.currency_pattern = re.compile(r'[^\d.\-]')  # Updated to handle negative numbers better

    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns from validation matrix."""
        self.patterns = {}
        for field_type, rules in self.validation_matrix.get('code_fields', {}).get('rules', {}).items():
            if 'pattern' in rules:
                self.patterns[field_type] = re.compile(rules['pattern'])
        
        # Add currency pattern
        self.currency_pattern = re.compile(r'[^\d.-]')

    def _clean_numeric_string(self, value: str) -> str:
        """Clean a numeric string by removing currency symbols and commas."""
        if not isinstance(value, str):
            value = str(value)
        # Handle empty strings and special values
        if not value.strip() or value.strip() in ['', 'None', 'null']:
            return ''
        cleaned = self.currency_pattern.sub('', value.strip())
        # Handle lone decimal point or minus sign
        if cleaned in ['.', '-', '-.']:
            return ''
        return cleaned

    def _convert_boolean(self, value: Any) -> bool:
        """Convert various boolean representations to Python bool."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            value = value.lower().strip()
            true_values = self.type_conversion.get('value_mapping', {}).get('true_values', 
                ['true', 'yes', 'y', '1', 't'])
            false_values = self.type_conversion.get('value_mapping', {}).get('false_values', 
                ['false', 'no', 'n', '0', 'f'])
            if value in true_values:
                return True
            if value in false_values:
                return False
        return bool(value)

    def _get_domain_mapping(self, mapping_name: str) -> Dict[str, str]:
        """Get domain mapping with proper fallbacks."""
        mapping = self.domain_mappings.get(mapping_name, {})
        if not mapping and '_' in mapping_name:
            # Try without suffix (e.g., 'action_type_code' -> 'action_type')
            base_name = mapping_name.rsplit('_', 1)[0]
            mapping = self.domain_mappings.get(base_name, {})
            
            # Try additional variations if still no mapping found
            if not mapping and base_name.endswith('_type'):
                # Try without '_type' suffix
                base_name = base_name[:-5]
                mapping = self.domain_mappings.get(base_name, {})
        return mapping

    def validate_csv_columns(self, csv_path: str) -> List[ValidationResult]:
        """Validate CSV columns against configuration.
        
        Args:
            csv_path: Path to CSV file to validate
        
        Returns:
            List of ValidationResult objects
        """
        results = []
        
        try:
            # Get encoding from config
            encoding = self.config['global']['encoding']
            
            with open(csv_path, 'r', encoding=encoding) as f:
                reader = csv.reader(f)
                headers = next(reader, None)
                
                if not headers:
                    results.append(ValidationResult(
                        valid=False,
                        message="CSV file is empty",
                        error_type="empty_file"
                    ))
                    return results
                
                # Validate essential fields exist
                essential_fields = self.config['contracts'].get('field_selection', {}).get('essential_fields', [])
                if essential_fields:
                    missing = [f for f in essential_fields if f not in headers]
                    if missing:
                        results.append(ValidationResult(
                            valid=False,
                            message=f"CSV missing essential fields: {', '.join(missing)}",
                            error_type="missing_essential_fields",
                            field_name=",".join(missing)
                        ))
                    
                # Validate entity key fields and field mappings
                entity_config = self.config['contracts'].get('entity_separation', {}).get('entities', {})
                for entity_type, cfg in entity_config.items():
                    # Get both key fields and field mappings
                    key_fields = set(cfg.get('key_fields', []))
                    field_mappings = cfg.get('field_mappings', {})
                    
                    # Convert field mappings to required source fields
                    required_source_fields = set()
                    for target, source in field_mappings.items():
                        if isinstance(source, str):
                            required_source_fields.add(source)
                        elif isinstance(source, (list, tuple)):
                            required_source_fields.update(source)
                    
                    # For recipient entity, we need to check field mappings instead of key fields
                    if entity_type == 'recipient':
                        # recipient_uei is mapped from the CSV field to uei in the entity
                        required_fields = required_source_fields
                    else:
                        # For other entities check both key fields and mappings
                        required_fields = required_source_fields.union(key_fields)
                    
                    if entity_type == 'agency':
                        # Special handling for agency fields with prefixes
                        prefixed_fields = set()
                        agency_prefixes = ['awarding_', 'funding_', 'parent_award_']
                        for field in required_fields:
                            prefixed_fields.update([f"{prefix}{field}" for prefix in agency_prefixes])
                        # Consider valid if any complete set of prefixed fields exists
                        valid_prefixes = []
                        for prefix in agency_prefixes:
                            prefix_fields = set(f"{prefix}{field}" for field in required_fields)
                            if prefix_fields.issubset(headers):
                                valid_prefixes.append(prefix)
                        if not valid_prefixes:
                            results.append(ValidationResult(
                                valid=False,
                                message=f"Missing required agency fields for {entity_type}",
                                error_type=f"missing_agency_fields_{entity_type}"
                            ))
                    else:
                        # For other entities check if required fields exist
                        missing = required_fields - set(headers)
                        if missing:
                            results.append(ValidationResult(
                                valid=False,
                                message=f"Missing required fields for {entity_type}: {', '.join(missing)}",
                                error_type=f"missing_required_fields_{entity_type}",
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
        """Validate award value relationships.
        
        Ensures that base_exercised_options_value doesn't exceed base_and_all_options_value.
        
        Args:
            data: Dictionary containing award values
            
        Returns:
            ValidationResult indicating if values are valid
        """
        if ('base_exercised_options_value' in data and 
            'base_and_all_options_value' in data):
            
            try:
                exercised = float(data['base_exercised_options_value'])
                total = float(data['base_and_all_options_value'])
                
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

    def validate_field(self, field_name: str, value: Any, rules: List[Dict[str, Any]], 
                      context: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Validate a single field against its rules."""
        # Get field type first
        field_type = self._get_field_type(field_name)
        
        # Check if field is required (only for essential fields)
        is_required = field_name in self.essential_fields

        # Handle empty/null values - match TypeConverter behavior
        if value is None or (isinstance(value, str) and not value.strip()) or str(value).strip().lower() in ('none', 'null', ''):
            if is_required:
                return ValidationResult(
                    valid=False,
                    message=f"Required field {field_name} is missing",
                    error_type=f"{field_type}_missing" if field_type else "required_field_missing",
                    field_name=field_name
                )
            # Non-required fields can be empty/null (match TypeConverter behavior)
            return ValidationResult(True, None)

        # Convert value to string for validation
        str_value = str(value).strip()

        # Apply type-specific validation
        if field_type:
            if field_type == 'numeric':
                try:
                    cleaned = self._clean_numeric_string(str_value)
                    if not cleaned:
                        # Empty after cleaning is valid for non-required fields (match TypeConverter)
                        return ValidationResult(True, None)
                    float(cleaned)  # Just validate format
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
                    # First try exact ISO format match (like TypeConverter)
                    if self.date_pattern.match(str_value):
                        return ValidationResult(True, None)
                    # Try parsing with datetime (for other formats)
                    parsed_date = datetime.strptime(str_value[:10], '%Y-%m-%d')
                    
                    # Cross-field date validation only if both dates are present and valid
                    if field_name == 'period_of_performance_start_date' and context:
                        end_date = context.get('period_of_performance_current_end_date')
                        if end_date and str(end_date).strip():
                            try:
                                end_date = datetime.strptime(str(end_date)[:10], '%Y-%m-%d')
                                if parsed_date > end_date:
                                    return ValidationResult(
                                        valid=False,
                                        message=f"Period of performance start date cannot be after end date",
                                        error_type="date_range_invalid",
                                        field_name=field_name
                                    )
                            except ValueError:
                                pass  # End date format error will be caught in its own validation
                except ValueError:
                    return ValidationResult(
                        valid=False,
                        message=f"Invalid date value for {field_name}",
                        error_type="date_invalid",
                        field_name=field_name
                    )

        # Domain value validation with improved matching
        for rule in rules:
            rule_type = rule.get('type')
            if rule_type == 'exists_in_mapping':
                mapping_name = rule.get('mapping', field_name)
                mapping = self._get_domain_mapping(mapping_name)
                
                if mapping:
                    str_value_upper = str_value.upper().strip()
                    # Try direct matches first
                    if str_value in mapping or str_value_upper in mapping:
                        return ValidationResult(True, None)
                        
                    # Try case-insensitive key matching
                    for key in mapping:
                        key_str = str(key).upper().strip()
                        if str_value_upper == key_str:
                            return ValidationResult(True, None)
                    
                    # Try matching against values (descriptions)
                    for val in mapping.values():
                        val_str = str(val).upper().strip()
                        if str_value_upper == val_str:
                            return ValidationResult(True, None)
                            
                    # Special case: If value is a single character, try matching as a code
                    if len(str_value_upper) == 1:
                        for key in mapping:
                            if str(key).upper().startswith(str_value_upper):
                                return ValidationResult(True, None)
                    
                    return ValidationResult(
                        valid=False,
                        message=f"Invalid domain value '{str_value}' for {field_name}. Valid values are: {', '.join(map(str, mapping.keys()))}",
                        error_type="domain_value_invalid",
                        field_name=field_name
                    )

        # Process remaining validation rules
        for rule in rules:
            rule_type = rule.get('type')
            if not rule_type:
                continue

            # Pattern validation
            if rule_type == 'pattern':
                pattern = rule.get('pattern')
                if pattern:
                    if field_name in self.patterns:
                        if not self.patterns[field_name].match(str_value):
                            return ValidationResult(
                                valid=False,
                                message=f"Invalid format for {field_name}",
                                error_type="pattern_mismatch",
                                field_name=field_name
                            )
                    else:
                        try:
                            if not re.match(pattern, str_value):
                                return ValidationResult(
                                    valid=False,
                                    message=f"Invalid format for {field_name}",
                                    error_type="pattern_mismatch",
                                    field_name=field_name
                                )
                        except re.error:
                            logger.error(f"Invalid pattern for {field_name}: {pattern}")
                            return ValidationResult(
                                valid=False,
                                message=f"Invalid pattern configured for {field_name}",
                                error_type="pattern_config_error",
                                field_name=field_name
                            )

            # Decimal precision validation
            elif rule_type == 'decimal':
                try:
                    str_val = self._clean_numeric_string(str_value)
                    if '.' in str_val:
                        decimal_places = len(str_val.split('.')[1])
                        max_precision = rule.get('precision', 
                            self.type_conversion.get('value_validation', {}).get('numeric', {}).get('decimal_places', 2))
                        if decimal_places > max_precision:
                            return ValidationResult(False, f"Too many decimal places in {field_name}")
                except (ValueError, IndexError):
                    return ValidationResult(False, f"Invalid decimal value for {field_name}")

            # Min/max value validation
            elif rule_type in ('min_value', 'max_value'):
                try:
                    num_val = float(self._clean_numeric_string(str_value))
                    limit = float(rule['value'])
                    if (rule_type == 'min_value' and num_val < limit) or \
                       (rule_type == 'max_value' and num_val > limit):
                        return ValidationResult(False, f"{field_name} outside allowed range")
                except (ValueError, TypeError):
                    return ValidationResult(False, f"Invalid numeric value for {field_name}")

            # Domain value validation with case-insensitive matching
            elif rule_type == 'exists_in_mapping':
                mapping_name = rule.get('mapping', field_name)
                mapping = self._get_domain_mapping(mapping_name)
                
                if mapping:
                    # Try exact match first, then case-insensitive
                    if str_value not in mapping:
                        found = False
                        str_value_upper = str_value.upper()
                        for key in mapping:
                            if str_value_upper == str(key).upper():
                                found = True
                                break
                        if not found:
                            return ValidationResult(
                                valid=False,
                                message=f"Invalid domain value '{str_value}' for {field_name}",
                                error_type="domain_value_invalid",
                                field_name=field_name
                            )

            # Cross-field comparison validation
            elif rule_type in ('greater_than', 'less_than', 'greater_than_or_equal', 'less_than_or_equal'):
                if not context or rule['field'] not in context:
                    continue
                try:
                    val1 = float(self._clean_numeric_string(str_value))
                    val2_str = str(context[rule['field']])
                    if val2_str.strip():  # Only compare if comparison value exists
                        val2 = float(self._clean_numeric_string(val2_str))
                        if not self._compare_values(val1, val2, rule_type):
                            return ValidationResult(False, 
                                f"Invalid relationship between {field_name} ({val1}) and {rule['field']} ({val2})")
                except (ValueError, TypeError):
                    return ValidationResult(False, f"Invalid numeric comparison for {field_name}")

            # Boolean validation
            elif rule_type == 'boolean':
                try:
                    self._convert_boolean(value)
                except ValueError:
                    return ValidationResult(False, f"Invalid boolean value for {field_name}")

        return ValidationResult(True, None)

    def _compare_values(self, val1: float, val2: float, comparison_type: str) -> bool:
        """Compare two values based on comparison type."""
        if comparison_type == 'greater_than':
            return val1 > val2
        elif comparison_type == 'less_than':
            return val1 < val2
        elif comparison_type == 'greater_than_or_equal':
            return val1 >= val2
        elif comparison_type == 'less_than_or_equal':
            return val1 <= val2
        return False

    def validate_entity(self, entity_type: str, data: Dict[str, Any], 
                       context: Optional[Dict[str, Any]] = None) -> List[ValidationResult]:
        """Validate an entire entity against its validation rules."""
        results: List[ValidationResult] = []
        
        # Special case for award value validations
        if entity_type == 'contract':
            # Validate award value relationships
            award_value_result = self.validate_award_values(data)
            if not award_value_result.valid:
                results.append(award_value_result)
        
        # Get the entity configuration based on path
        config_parts = entity_type.split('.')
        if len(config_parts) > 1:
            # For nested paths like 'contracts.transaction'
            entity_config = self.config.get(config_parts[0], {})
            entity_config = entity_config.get('entity_separation', {}).get('entities', {}).get(config_parts[1])
        else:
            # For simple paths
            entity_config = self.config.get('entity_separation', {}).get('entities', {}).get(entity_type)
            
        # If no validation rules found, return error
        if not entity_config:
            return [ValidationResult(
                valid=False,
                message=f"No validation configuration found for entity type: {entity_type}",
                error_type="config_not_found",
                field_name=entity_type
            )]
        
        if 'validation_rules' not in entity_config:
            return [ValidationResult(
                valid=False,
                message=f"No validation rules defined for entity type: {entity_type}",
                error_type="rules_not_found",
                field_name=entity_type
            )]

        # Cache entity config and rules per type if not already cached
        if not hasattr(self, '_entity_config_cache'):
            self._entity_config_cache = {}
        
        if entity_type not in self._entity_config_cache:
            config_parts = entity_type.split('.')
            if len(config_parts) > 1:
                entity_config = self.config.get(config_parts[0], {})
                entity_config = entity_config.get('entity_separation', {}).get('entities', {}).get(config_parts[1])
            else:
                entity_config = self.config.get('entity_separation', {}).get('entities', {}).get(entity_type)
            
            if not entity_config or 'validation_rules' not in entity_config:
                return [ValidationResult(
                    valid=False,
                    message=f"No validation configuration found for entity type: {entity_type}",
                    error_type="config_not_found",
                    field_name=entity_type
                )]
            
            self._entity_config_cache[entity_type] = entity_config
        
        entity_config = self._entity_config_cache[entity_type]
        validation_rules = entity_config['validation_rules']
        
        # Process each validation category
        for category, field_list in validation_rules.items():
            if not isinstance(field_list, list):
                logger.warning(f"Skipping invalid field list for category {category}")
                continue
                
            # Skip special categories like business_characteristics
            if category == 'business_characteristics':
                characteristic_results = self.validate_business_characteristics(data)
                results.extend(characteristic_results)
                continue
                
            for field_config in field_list:
                if not isinstance(field_config, dict):
                    logger.warning(f"Skipping invalid field config in category {category}")
                    continue
                    
                field_name = field_config.get('field')
                if not field_name:
                    continue
                    
                field_value = None
                
                # Handle nested fields (e.g. address.city)
                if '.' in field_name:
                    parts = field_name.split('.')
                    current = data
                    for part in parts:
                        if not isinstance(current, dict):
                            break
                        current = current.get(part, {})
                    if isinstance(current, (str, int, float, bool)):
                        field_value = current
                else:
                    field_value = data.get(field_name)

                # Validate the field
                result = self.validate_field(
                    field_name, 
                    field_value,
                    field_config.get('rules', []),
                    context or data  # Use full entity as context if none provided
                )
                if not result.valid:
                    # Add category to error type
                    error_type = f"{category}_{result.error_type}" if hasattr(result, 'error_type') else category
                    results.append(ValidationResult(
                        valid=False,
                        message=result.message if hasattr(result, 'message') else None,
                        error_type=error_type,
                        field_name=field_name
                    ))

        return results

    def validate_business_characteristics(self, data: Dict[str, Any]) -> List[ValidationResult]:
        """Validate business characteristics for mutual exclusivity."""
        results = []
        if 'characteristics' not in data:
            return results

        # Get characteristic validation rules
        entity_config = self.config.get('contracts', {}).get('entity_separation', {}).get('entities', {}).get('recipient', {})
        if not entity_config:
            return results
            
        rules = entity_config.get('validation_rules', {}).get('business_characteristics', {})
        
        # Check each category's rules
        for category, category_rules in rules.items():
            for rule in category_rules.get('rules', []):
                if rule['type'] == 'mutually_exclusive':
                    fields = rule['fields']
                    # Count true values in the mutually exclusive group
                    true_fields = [f for f in fields if data['characteristics'].get(f, False)]
                    if len(true_fields) > 1:
                        results.append(ValidationResult(
                            valid=False, 
                            message=f"Mutually exclusive fields in {category} cannot be true together: {', '.join(true_fields)}",
                            error_type=f"business_characteristics_{category}",
                            field_name=",".join(true_fields)
                        ))

        return results

    def _get_field_type(self, field_name: str) -> Optional[str]:
        """Determine the type of a field based on configuration."""
        # Use cached sets for faster lookups
        if field_name in self.date_fields:
            return 'date'
        if field_name in self.numeric_fields:
            return 'numeric'
        if field_name in self.boolean_fields:
            return 'boolean'
        
        # Check validation rules cache
        field_rules = self.field_rules_cache.get(field_name, [])
        for rule in field_rules:
            if rule.get('type') == 'type':
                return rule.get('value')
        return None

    def _get_field_validation_rules(self, field_name: str) -> List[Dict[str, Any]]:
        """Get validation rules for a field from the type_conversion configuration."""
        # Use cached rules
        return self.field_rules_cache.get(field_name, [])

    def _cache_config_values(self) -> None:
        """Cache commonly accessed configuration values for better performance."""
        # Cache date fields
        self.date_fields = set(self.type_conversion.get('date_fields', []))
        self.numeric_fields = set(self.type_conversion.get('numeric_fields', []))
        self.boolean_fields = set(self.type_conversion.get('boolean_fields', []))
        
        # Pre-compile validation rules by field
        self.field_rules_cache = {}
        validation_rules = self.validation_rules
        if validation_rules:
            for category in ('numeric', 'date'):
                rules = validation_rules.get(category, {}).get('validation_rules', [])
                for rule_config in rules:
                    field = rule_config.get('field')
                    if field:
                        if field not in self.field_rules_cache:
                            self.field_rules_cache[field] = []
                        self.field_rules_cache[field].extend(rule_config.get('rules', []))