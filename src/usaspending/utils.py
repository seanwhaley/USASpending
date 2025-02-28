"""Utility functions and classes for data processing."""
import re
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Union
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
        """Initialize type converter with configuration.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        type_config = config.get('type_conversion', {})
        
        # Get field type configurations
        self.date_fields = set(type_config.get('date_fields', []))
        self.numeric_fields = set(type_config.get('numeric_fields', []))
        self.boolean_fields = set(type_config.get('boolean_fields', []))
        
        # Get type conversion settings
        self.boolean_true = set(type_config.get('value_mapping', {}).get('true_values', 
            ['true', 'yes', 'y', '1', 't']))
        self.boolean_false = set(type_config.get('value_mapping', {}).get('false_values',
            ['false', 'no', 'n', '0', 'f']))
        
        # Compile regex patterns
        self.numeric_pattern = re.compile(r'[^0-9.-]')
        self.date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}')
        
        # Configure caching
        self._value_cache: Dict[str, Any] = {}
        self._pattern_cache: Dict[str, bool] = {}
        self.max_cache_size = 10000
        
    def _clean_numeric(self, value: str) -> str:
        """Remove non-numeric characters except decimal point and negative sign."""
        return self.numeric_pattern.sub('', value)
        
    def _get_cached_value(self, cache_key: str) -> Optional[Any]:
        """Get a cached converted value if available."""
        if len(self._value_cache) > self.max_cache_size:
            self._value_cache.clear()  # Simple cache clearing strategy
        return self._value_cache.get(cache_key)
        
    def _cache_value(self, cache_key: str, value: Any) -> None:
        """Cache a converted value."""
        if len(self._value_cache) <= self.max_cache_size:
            self._value_cache[cache_key] = value
            
    def convert_value(self, value: Any, field_name: str) -> Any:
        """Convert a value based on field type with caching."""
        if value is None:
            return None
            
        # Make value string for consistent handling
        str_value = str(value).strip().lower()
        if not str_value:
            return None
            
        # Generate cache key
        cache_key = f"{field_name}:{str_value}"
        cached = self._get_cached_value(cache_key)
        if cached is not None:
            return cached
            
        # Convert based on field type
        if field_name in self.numeric_fields:
            try:
                cleaned = self._clean_numeric(str_value)
                if '.' in cleaned:
                    result = float(cleaned)
                else:
                    result = int(cleaned)
                self._cache_value(cache_key, result)
                return result
            except (ValueError, TypeError):
                return None
                
        elif field_name in self.date_fields:
            try:
                # First try exact ISO format
                if self.date_pattern.match(str_value):
                    result = str_value[:10]  # YYYY-MM-DD
                    self._cache_value(cache_key, result)
                    return result
                # Try parsing with datetime
                dt = datetime.strptime(str_value[:10], '%Y-%m-%d')
                result = dt.strftime('%Y-%m-%d')
                self._cache_value(cache_key, result)
                return result
            except (ValueError, TypeError):
                return None
                
        elif field_name in self.boolean_fields:
            if str_value in self.boolean_true:
                self._cache_value(cache_key, True)
                return True
            elif str_value in self.boolean_false:
                self._cache_value(cache_key, False)
                return False
            return None
            
        # For all other fields, return cleaned string value
        self._cache_value(cache_key, str_value)
        return str_value

    def validate_type(self, value: Any, field_name: str) -> bool:
        """Validate that a value matches its expected type."""
        if value is None:
            return True  # None is valid for any type
            
        str_value = str(value).strip().lower()
        if not str_value:
            return True
            
        # Check numeric fields
        if field_name in self.numeric_fields:
            try:
                cleaned = self._clean_numeric(str_value)
                float(cleaned)  # Just try conversion
                return True
            except (ValueError, TypeError):
                return False
                
        # Check date fields
        elif field_name in self.date_fields:
            try:
                if self.date_pattern.match(str_value):
                    return True
                datetime.strptime(str_value[:10], '%Y-%m-%d')
                return True
            except (ValueError, TypeError):
                return False
                
        # Check boolean fields
        elif field_name in self.boolean_fields:
            return str_value in self.boolean_true or str_value in self.boolean_false
            
        # All other fields are valid
        return True