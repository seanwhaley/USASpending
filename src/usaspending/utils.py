"""Utility functions and classes for data processing."""
import re
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Union, Callable
import logging

logger = logging.getLogger(__name__)

def generate_entity_key(entity_type: str, key_fields: Dict[str, Any]) -> str:
    """Generate a unique key for an entity based on key fields."""
    if not key_fields:
        raise ValueError("Key fields cannot be empty")
    
    key_parts = [str(key_fields.get(k, '')) for k in sorted(key_fields.keys())]
    return f"{entity_type}:{':'.join(key_parts)}"

class TypeConverter:
    """Converts and validates data types based on configuration."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize type converter with config.
        
        Args:
            config: Configuration with type conversion rules
        """
        self.config = config
        self.string_patterns = config.get("string_patterns", {})
        self._cache = {}
        self.max_cache_size = 1000
        
        # Default validation patterns
        self._validation_patterns = {
            "phone": r"^\+?1?\d{9,15}$",
            "email": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
            "zip": r"^\d{5}(?:-\d{4})?$",
            "url": r"^https?://[^\s/$.?#].[^\s]*$"
        }
        
        # Default true/false values for boolean conversion
        self._true_values = ["true", "yes", "1"]
        self._false_values = ["false", "no", "0"]

    def convert_value(self, value: Any, field_name_or_type: str) -> Any:
        """
        Convert a value based on field name or explicit type.
        
        Args:
            value: The value to convert
            field_name_or_type: Either a field name (to determine type from naming convention)
                                or an explicit field type like "money"
        
        Returns:
            Converted value, or None if conversion failed
        """
        if value is None:
            return None
            
        # Use cache if available
        cache_key = (str(value), field_name_or_type)
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        result = None
        
        # Handle explicit types (when called with field_type directly)
        if field_name_or_type in ["money", "decimal", "integer", "date", "boolean", "phone", "zip", "email", "url"]:
            if field_name_or_type == "money":
                result = self._convert_money(value)
            elif field_name_or_type == "decimal":
                result = self._convert_decimal(value)
            elif field_name_or_type == "integer":
                result = self._convert_integer(value)
            elif field_name_or_type == "date":
                result = self._convert_date(value)
            elif field_name_or_type == "boolean":
                result = self._convert_boolean(value)
            elif field_name_or_type == "phone":
                result = self._convert_phone(value)
            elif field_name_or_type == "zip":
                result = self._convert_zip(value)
        else:
            # Handle field name-based conversions
            field_name = field_name_or_type
            
            # Handle money fields
            if field_name in ["amount", "total"]:
                result = self._convert_money(value)
            # Handle numeric fields
            elif field_name in ["rate", "percentage"]:
                result = self._convert_decimal(value)
            elif field_name in ["count", "quantity"]:
                result = self._convert_integer(value)
            # Handle date fields
            elif field_name.startswith("date_") or field_name in ["created_at", "updated_at"]:
                result = self._convert_date(value)
            # Handle boolean fields
            elif field_name.startswith("is_") or field_name.startswith("has_") or field_name == "active":
                result = self._convert_boolean(value)
            # Handle custom types
            elif field_name == "phone":
                result = self._convert_phone(value)
            elif field_name == "zip":
                result = self._convert_zip(value)
            else:
                # Default is to return the value as is
                result = value
            
        # Cache the result
        if len(self._cache) >= self.max_cache_size:
            self._cache.clear()
        self._cache[cache_key] = result
        
        return result
        
    def validate_type(self, value: Any, type_name: str) -> bool:
        """
        Validate a value against a type.
        
        Args:
            value: The value to validate
            type_name: The type to validate against
            
        Returns:
            True if value is valid for the type, False otherwise
        """
        if value is None:
            return False
            
        if type_name in self._validation_patterns:
            pattern = self._validation_patterns[type_name]
            return bool(re.match(pattern, str(value)))
            
        # Default validation (always pass)
        return True
        
    def _convert_money(self, value: str) -> Optional[float]:
        """Convert money string to float."""
        try:
            # Remove currency symbols and commas
            clean_value = str(value)
            for char in "$,":  # Changed from "$,." to "$," to preserve decimal point
                clean_value = clean_value.replace(char, "")
            return float(clean_value)
        except (ValueError, TypeError):
            return None
            
    def _convert_decimal(self, value: str) -> Optional[float]:
        """Convert decimal string to float."""
        try:
            # Remove commas
            clean_value = str(value).replace(",", "")
            return float(clean_value)
        except (ValueError, TypeError):
            return None
            
    def _convert_integer(self, value: str) -> Optional[int]:
        """Convert integer string to int."""
        try:
            # Remove commas and decimal part
            clean_value = str(value).replace(",", "")
            return int(float(clean_value))
        except (ValueError, TypeError):
            return None
            
    def _convert_date(self, value: str) -> Optional[str]:
        """Convert date string to standard format."""
        try:
            # For now, just validate it's a valid date string
            # In a real implementation, this would parse and format the date
            if re.match(r'^\d{4}-\d{2}-\d{2}$', str(value)):
                return str(value)
            return None
        except (ValueError, TypeError):
            return None
            
    def _convert_boolean(self, value: str) -> Optional[bool]:
        """Convert string to boolean."""
        value_lower = str(value).lower()
        if value_lower in self._true_values:
            return True
        elif value_lower in self._false_values:
            return False
        return None
        
    def _convert_phone(self, value: str) -> Optional[str]:
        """Convert phone number to standard format."""
        if not self.validate_type(value, "phone"):
            return None
            
        # Format as (XXX) XXX-XXXX if 10 digits
        if re.match(r'^\d{10}$', str(value)):
            return f"({value[:3]}) {value[3:6]}-{value[6:]}"
        return str(value)
        
    def _convert_zip(self, value: str) -> Optional[str]:
        """Convert ZIP code to standard format."""
        if not self.validate_type(value, "zip"):
            # Try to format as XXXXX-XXXX if 9 digits
            if re.match(r'^\d{9}$', str(value)):
                return f"{value[:5]}-{value[5:]}"
            return None
        return str(value)