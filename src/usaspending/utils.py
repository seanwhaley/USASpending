"""Utility functions and classes for data processing."""
import re
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Union, Callable
import logging

logger = logging.getLogger(__name__)

def generate_entity_key(entity_type: str, key_data: Dict[str, Any], key_fields: List[str]) -> str:
    """Generate a unique key for an entity.
    
    Args:
        entity_type: Type of entity
        key_data: Dictionary containing key field values
        key_fields: List of fields to use for key generation
        
    Returns:
        Generated entity key
    """
    # First try natural key from key fields
    key_parts = []
    for field in key_fields:
        if field not in key_data:
            return ""
        value = str(key_data[field]).strip()
        if not value:
            return ""
        key_parts.append(value)
    
    return "_".join([entity_type] + key_parts)

class TypeConverter:
    """Handles performance-critical type conversions with caching."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize type converter with configuration."""
        self.config = config
        
        # Initialize validation types from config
        self.validation_types = config.get('validation_types', {})
        
        # Extract field type configurations
        self._build_field_type_sets()
        
        # Initialize patterns and formats
        self._init_patterns_and_formats()
        
        # Initialize custom type handlers
        self._init_custom_types()
        
        # Configure caching
        self._value_cache: Dict[str, Any] = {}
        self._pattern_cache: Dict[str, bool] = {}
        self.max_cache_size = config.get('global', {}).get('processing', {}).get('max_cache_size', 10000)

    def _init_patterns_and_formats(self) -> None:
        """Initialize validation patterns and formats from config."""
        # Get numeric config
        numeric_config = self.validation_types.get('numeric', {})
        
        # Get pattern chars for different numeric types
        decimal_chars = numeric_config.get('decimal', {}).get('strip_characters', '$,.')
        money_chars = numeric_config.get('money', {}).get('strip_characters', '$,.')
        
        # Compile numeric patterns
        self.decimal_pattern = re.compile(f'[{re.escape(decimal_chars)}]')
        self.money_pattern = re.compile(f'[{re.escape(money_chars)}]')
        
        # Get date formats
        date_config = self.validation_types.get('date', {})
        self.date_format = date_config.get('standard', {}).get('format', '%Y-%m-%d')
        self.date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}')
        
        # Get string patterns
        self.string_patterns = self.validation_types.get('string', {}).get('pattern', {})
        
        # Get boolean values
        bool_config = self.validation_types.get('boolean', {}).get('validation', {})
        self.boolean_true = set(bool_config.get('true_values', ['true', 'yes', 'y', '1', 't', 'T']))
        self.boolean_false = set(bool_config.get('false_values', ['false', 'no', 'n', '0', 'f', 'F']))

    def _init_custom_types(self) -> None:
        """Initialize custom type handlers from config."""
        self.custom_types = {}
        custom_config = self.validation_types.get('custom', {})
        
        for type_name, type_config in custom_config.items():
            validator = type_config.get('validator')
            if validator:
                try:
                    # Get validator function
                    validator_fn = getattr(self, f"_validate_{validator}")
                    conversion_fn = getattr(self, f"_convert_{validator}", None)
                    self.custom_types[type_name] = {
                        'validator': validator_fn,
                        'converter': conversion_fn,
                        'config': type_config
                    }
                except AttributeError:
                    logger.warning(f"Custom validator {validator} not found")

    def _build_field_type_sets(self) -> None:
        """Build sets of fields by type from the configuration."""
        type_config = self.config.get('type_conversion', {})
        
        self.field_sets = {
            'date': set(),
            'numeric': {
                'decimal': set(),
                'money': set(),
                'integer': set()
            },
            'boolean': set(),
            'string': {
                'pattern': {},
                'length': {}
            }
        }
        
        # Process date fields
        for group in type_config.get('date', {}).get('fields', []):
            if isinstance(group, dict) and 'fields' in group:
                self.field_sets['date'].update(self._expand_field_patterns(group['fields']))
        
        # Process numeric fields
        for group in type_config.get('numeric', {}).get('fields', []):
            if isinstance(group, dict) and 'fields' in group:
                ref = group.get('$ref', '')
                fields = self._expand_field_patterns(group['fields'])
                
                if 'numeric.money' in ref:
                    self.field_sets['numeric']['money'].update(fields)
                elif 'numeric.decimal' in ref:
                    self.field_sets['numeric']['decimal'].update(fields)
                elif 'numeric.integer' in ref:
                    self.field_sets['numeric']['integer'].update(fields)
                else:
                    # Default to decimal if no specific type
                    self.field_sets['numeric']['decimal'].update(fields)
        
        # Process boolean fields
        for group in type_config.get('boolean', {}).get('fields', []):
            if isinstance(group, dict) and 'fields' in group:
                self.field_sets['boolean'].update(self._expand_field_patterns(group['fields']))
        
        # Process string pattern fields
        for pattern_name, pattern in self.string_patterns.items():
            self.field_sets['string']['pattern'][pattern_name] = re.compile(pattern)

    def _expand_field_patterns(self, fields: List[str]) -> Set[str]:
        """Expand field patterns with wildcards into concrete field names."""
        expanded = set()
        for field in fields:
            if '*' in field or '[' in field:
                # Handle array index patterns like [1-5]
                if '[' in field and ']' in field:
                    base = field[:field.index('[')]
                    range_str = field[field.index('[')+1:field.index(']')]
                    if '-' in range_str:
                        start, end = map(int, range_str.split('-'))
                        for i in range(start, end + 1):
                            expanded.add(f"{base}{i}")
                    continue
                
                # Convert glob pattern to regex
                pattern = field.replace('*', '.*')
                regex = re.compile(f"^{pattern}$")
                
                # Check against all known fields from validation matrix
                all_fields = set(self.config.get('validation_matrix', {}).keys())
                expanded.update(f for f in all_fields if regex.match(f))
            else:
                expanded.add(field)
        return expanded

    def convert_value(self, value: Any, field_type: str) -> Any:
        """Convert a value based on field type with caching.
        
        Args:
            value: Value to convert
            field_type: Field type or name (can be custom type or field name)
            
        Returns:
            Converted value
        """
        if value is None:
            return None
            
        # Make value string for consistent handling
        str_value = str(value).strip()
        if not str_value:
            return None
            
        # Generate cache key
        cache_key = f"{field_type}:{str_value}"
        cached = self._get_cached_value(cache_key)
        if cached is not None:
            return cached
            
        # Try custom type conversion first
        if field_type in self.custom_types and self.custom_types[field_type]['converter']:
            try:
                result = self.custom_types[field_type]['converter'](
                    str_value,
                    **self.custom_types[field_type]['config'].get('args', {})
                )
                if result is not None:
                    self._cache_value(cache_key, result)
                    return result
            except Exception as e:
                logger.debug(f"Custom conversion failed for {field_type}: {str(e)}")
        
        # Fall back to standard field-based conversion
        result = self._convert_by_field(str_value, field_type)
        self._cache_value(cache_key, result)
        return result

    def _convert_by_field(self, str_value: str, field_name: str) -> Any:
        """Convert value based on field type configuration."""
        result = None
        
        # Check numeric fields
        if any(field_name in fields for fields in self.field_sets['numeric'].values()):
            try:
                if field_name in self.field_sets['numeric']['money']:
                    cleaned = self.money_pattern.sub('', str_value)
                    result = float(cleaned)
                elif field_name in self.field_sets['numeric']['decimal']:
                    cleaned = self.decimal_pattern.sub('', str_value)
                    result = float(cleaned)
                elif field_name in self.field_sets['numeric']['integer']:
                    cleaned = self.decimal_pattern.sub('', str_value)
                    result = int(float(cleaned))
            except (ValueError, TypeError):
                result = None
                
        # Check date fields
        elif field_name in self.field_sets['date']:
            try:
                if self.date_pattern.match(str_value):
                    result = str_value[:10]
                else:
                    dt = datetime.strptime(str_value[:10], self.date_format)
                    result = dt.strftime('%Y-%m-%d')
            except (ValueError, TypeError):
                result = None
                
        # Check boolean fields
        elif field_name in self.field_sets['boolean']:
            str_value = str_value.lower()
            if str_value in self.boolean_true:
                result = True
            elif str_value in self.boolean_false:
                result = False
            else:
                result = None
                
        # Check string pattern fields
        else:
            for pattern_name, pattern in self.field_sets['string']['pattern'].items():
                if pattern.match(str_value):
                    result = str_value
                    break
            if result is None:
                result = str_value
                
        return result

    def validate_type(self, value: Any, field_type: str) -> bool:
        """Validate that a value matches its expected type.
        
        Args:
            value: Value to validate
            field_type: Field type or name (can be custom type or field name)
            
        Returns:
            True if value is valid for the type
        """
        # Check custom type validation first
        if field_type in self.custom_types:
            try:
                return self.custom_types[field_type]['validator'](
                    value,
                    **self.custom_types[field_type]['config'].get('args', {})
                )
            except Exception as e:
                logger.debug(f"Custom validation failed for {field_type}: {str(e)}")
                return False
        
        # Fall back to standard conversion-based validation
        converted = self.convert_value(value, field_type)
        if converted is None and value is not None:
            return False
        return True

    # Custom type validation methods
    def _validate_url(self, value: str, **kwargs) -> bool:
        """Validate URL format."""
        if not value:
            return False
        pattern = kwargs.get('pattern', r'^https?://[^\s/$.?#].[^\s]*$')
        return bool(re.match(pattern, str(value)))

    def _validate_phone(self, value: str, **kwargs) -> bool:
        """Validate phone number format."""
        if not value:
            return False
        pattern = kwargs.get('pattern', r'^\+?1?\d{9,15}$')
        return bool(re.match(pattern, re.sub(r'[\s\-\(\)]', '', str(value))))

    def _validate_email(self, value: str, **kwargs) -> bool:
        """Validate email format."""
        if not value:
            return False
        pattern = kwargs.get('pattern', r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        return bool(re.match(pattern, str(value)))

    def _validate_zip(self, value: str, **kwargs) -> bool:
        """Validate ZIP code format."""
        if not value:
            return False
        pattern = kwargs.get('pattern', r'^\d{5}(?:-\d{4})?$')
        return bool(re.match(pattern, str(value)))

    # Custom type conversion methods
    def _convert_phone(self, value: str, **kwargs) -> Optional[str]:
        """Normalize phone number format."""
        if not self._validate_phone(value, **kwargs):
            return None
        # Remove all non-digits
        digits = re.sub(r'\D', '', str(value))
        # Format as (XXX) XXX-XXXX if US number
        if len(digits) == 10:
            return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        return digits

    def _convert_zip(self, value: str, **kwargs) -> Optional[str]:
        """Normalize ZIP code format."""
        if not self._validate_zip(value, **kwargs):
            return None
        digits = re.sub(r'\D', '', str(value))
        if len(digits) == 9:
            return f"{digits[:5]}-{digits[5:]}"
        return digits[:5]

    def _get_cached_value(self, cache_key: str) -> Optional[Any]:
        """Get a cached converted value if available."""
        if len(self._value_cache) > self.max_cache_size:
            self._value_cache.clear()
        return self._value_cache.get(cache_key)

    def _cache_value(self, cache_key: str, value: Any) -> None:
        """Cache a converted value."""
        if len(self._value_cache) <= self.max_cache_size:
            self._value_cache[cache_key] = value