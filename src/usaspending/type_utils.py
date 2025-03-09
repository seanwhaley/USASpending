"""Type conversion and data manipulation utilities."""
from typing import Any, Dict, List, Optional, Union, TypeVar, Type, cast
from datetime import datetime, date
import decimal
from enum import Enum
from functools import lru_cache

from .exceptions import TypeConversionError

# Type definitions
T = TypeVar('T')
Number = Union[int, float, decimal.Decimal]
DateType = Union[date, datetime]

class TypeConverter:
    """Utility class for type conversions with caching."""
    
    @staticmethod
    @lru_cache(maxsize=1024)
    def to_bool(value: Any) -> bool:
        """Convert value to boolean with caching.
        
        Args:
            value: Value to convert
            
        Returns:
            Boolean value
            
        Raises:
            TypeConversionError: If value cannot be converted
        """
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            value = value.lower().strip()
            if value in ('true', 't', 'yes', 'y', '1', 'on'):
                return True
            if value in ('false', 'f', 'no', 'n', '0', 'off'):
                return False
        raise TypeConversionError(f"Cannot convert {value} to boolean")
    
    @staticmethod
    @lru_cache(maxsize=1024)
    def to_number(value: Any, decimal_places: Optional[int] = None) -> Number:
        """Convert value to number with optional decimal places.
        
        Args:
            value: Value to convert
            decimal_places: Number of decimal places to round to
            
        Returns:
            Numeric value
            
        Raises:
            TypeConversionError: If value cannot be converted
        """
        try:
            if isinstance(value, (int, float, decimal.Decimal)):
                num = decimal.Decimal(str(value))
            elif isinstance(value, str):
                value = value.strip().replace(',', '')
                num = decimal.Decimal(value)
            else:
                raise TypeConversionError(f"Cannot convert {value} to number")
                
            if decimal_places is not None:
                return float(round(num, decimal_places))
            return float(num)
        except (ValueError, decimal.InvalidOperation) as e:
            raise TypeConversionError(f"Cannot convert {value} to number: {str(e)}")
    
    @staticmethod
    @lru_cache(maxsize=1024)
    def to_date(value: Any, fmt: Optional[str] = None) -> DateType:
        """Convert value to date/datetime.
        
        Args:
            value: Value to convert
            fmt: Optional date format string
            
        Returns:
            Date or datetime object
            
        Raises:
            TypeConversionError: If value cannot be converted
        """
        if isinstance(value, (date, datetime)):
            return value
            
        if not isinstance(value, str):
            raise TypeConversionError(f"Cannot convert {value} to date")
            
        value = value.strip()
        if not value:
            raise TypeConversionError("Cannot convert empty string to date")
            
        if fmt:
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError as e:
                raise TypeConversionError(f"Cannot convert {value} to date using format {fmt}: {str(e)}")
                
        formats = [
            '%Y-%m-%d',
            '%m/%d/%Y',
            '%Y/%m/%d',
            '%d-%m-%Y',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%d %H:%M:%S.%f'
        ]
        
        for fmt in formats:
            try:
                parsed = datetime.strptime(value, fmt)
                return parsed.date() if fmt.count(':') == 0 else parsed
            except ValueError:
                continue
                
        raise TypeConversionError(f"Cannot convert {value} to date using any known format")
    
    @staticmethod
    def to_enum(value: Any, enum_class: Type[Enum]) -> Enum:
        """Convert value to enum.
        
        Args:
            value: Value to convert
            enum_class: Enum class to convert to
            
        Returns:
            Enum value
            
        Raises:
            TypeConversionError: If value cannot be converted
        """
        if isinstance(value, enum_class):
            return value
            
        try:
            if isinstance(value, str):
                # Try by name
                return enum_class[value.upper()]
            elif isinstance(value, int):
                # Try by value
                return enum_class(value)
        except (KeyError, ValueError) as e:
            raise TypeConversionError(f"Cannot convert {value} to {enum_class.__name__}: {str(e)}")
    
    @staticmethod
    def coerce_type(value: Any, target_type: Union[str, Type[T]]) -> T:
        """Coerce value to target type.
        
        Args:
            value: Value to convert
            target_type: Target type (string name or type object)
            
        Returns:
            Converted value
            
        Raises:
            TypeConversionError: If value cannot be converted
        """
        if isinstance(target_type, str):
            type_map = {
                'str': str,
                'string': str,
                'int': int,
                'integer': int,
                'float': float,
                'bool': bool,
                'boolean': bool,
                'date': date,
                'datetime': datetime,
                'number': TypeConverter.to_number,
                'decimal': decimal.Decimal
            }
            try:
                target_type = type_map[target_type.lower()]
            except KeyError:
                raise TypeConversionError(f"Unknown target type: {target_type}")
        
        try:
            if target_type in (bool, 'bool', 'boolean'):
                return cast(T, TypeConverter.to_bool(value))
            elif target_type in (date, datetime, 'date', 'datetime'):
                return cast(T, TypeConverter.to_date(value))
            elif target_type in (TypeConverter.to_number, 'number', float, decimal.Decimal):
                return cast(T, TypeConverter.to_number(value))
            else:
                return target_type(value)
        except (ValueError, TypeError) as e:
            raise TypeConversionError(f"Cannot convert {value} to {target_type}: {str(e)}")

# Exports
__all__ = ['TypeConverter']