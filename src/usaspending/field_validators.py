"""Field validation implementations."""
from typing import Dict, Any, List, Optional, Pattern
import re
from datetime import datetime
import logging

from .interfaces import IFieldValidator
from .validation_base import BaseValidator

logger = logging.getLogger(__name__)

class PatternValidator(BaseValidator, IFieldValidator):
    """Validates fields against regex patterns."""
    
    def __init__(self, pattern: str, flags: int = 0):
        """Initialize with regex pattern."""
        super().__init__()
        try:
            self._pattern = re.compile(pattern, flags)
        except re.error as e:
            logger.error(f"Invalid regex pattern '{pattern}': {str(e)}")
            raise ValueError(f"Invalid regex pattern: {str(e)}")

    def validate(self, value: Any, context: Optional[Dict[str, Any]] = None) -> bool:
        """Validate value against pattern."""
        if value is None:
            self.add_error("Value cannot be None", "null_value")
            return False
            
        try:
            str_value = str(value)
            if self._pattern.match(str_value):
                return True
            
            self.add_error(
                f"Value '{value}' does not match pattern {self._pattern.pattern}",
                "pattern_mismatch",
                {'value': value, 'pattern': self._pattern.pattern}
            )
            return False
            
        except Exception as e:
            self.add_error(f"Pattern validation failed: {str(e)}", "validation_error")
            return False

class DateValidator(BaseValidator, IFieldValidator):
    """Validates date fields."""
    
    def __init__(self, formats: List[str] = None):
        """Initialize with date formats."""
        super().__init__()
        self._formats = formats or [
            '%Y-%m-%d',
            '%Y/%m/%d',
            '%m/%d/%Y',
            '%d/%m/%Y',
            '%Y%m%d'
        ]

    def validate(self, value: Any, context: Optional[Dict[str, Any]] = None) -> bool:
        """Validate date value."""
        if value is None:
            self.add_error("Date value cannot be None", "null_value")
            return False
            
        str_value = str(value).strip()
        if not str_value:
            self.add_error("Date value cannot be empty", "empty_value")
            return False
            
        for fmt in self._formats:
            try:
                datetime.strptime(str_value, fmt)
                return True
            except ValueError:
                continue
                
        self.add_error(
            f"Value '{value}' is not a valid date",
            "invalid_date",
            {'value': value, 'accepted_formats': self._formats}
        )
        return False

class NumericValidator(BaseValidator, IFieldValidator):
    """Validates numeric fields."""
    
    def __init__(self, min_value: Optional[float] = None,
                 max_value: Optional[float] = None,
                 allow_negative: bool = True):
        """Initialize with numeric constraints."""
        super().__init__()
        self._min = min_value
        self._max = max_value
        self._allow_negative = allow_negative

    def validate(self, value: Any, context: Optional[Dict[str, Any]] = None) -> bool:
        """Validate numeric value."""
        if value is None:
            self.add_error("Numeric value cannot be None", "null_value")
            return False
            
        try:
            num_value = float(value)
            
            if not self._allow_negative and num_value < 0:
                self.add_error(
                    f"Negative values not allowed: {value}",
                    "negative_value",
                    {'value': value}
                )
                return False
                
            if self._min is not None and num_value < self._min:
                self.add_error(
                    f"Value {value} below minimum {self._min}",
                    "below_minimum",
                    {'value': value, 'minimum': self._min}
                )
                return False
                
            if self._max is not None and num_value > self._max:
                self.add_error(
                    f"Value {value} above maximum {self._max}",
                    "above_maximum",
                    {'value': value, 'maximum': self._max}
                )
                return False
                
            return True
            
        except (ValueError, TypeError) as e:
            self.add_error(
                f"Invalid numeric value '{value}': {str(e)}",
                "invalid_number",
                {'value': value}
            )
            return False

class CodeValidator(BaseValidator, IFieldValidator):
    """Validates code fields against allowed values."""
    
    def __init__(self, valid_codes: List[str],
                 case_sensitive: bool = False,
                 allow_pattern: bool = False):
        """Initialize with valid codes."""
        super().__init__()
        self._case_sensitive = case_sensitive
        self._allow_pattern = allow_pattern
        
        if case_sensitive:
            self._valid_codes = set(valid_codes)
        else:
            self._valid_codes = {c.upper() for c in valid_codes}
            
        if allow_pattern:
            try:
                self._patterns = [re.compile(c) for c in valid_codes]
            except re.error as e:
                logger.error(f"Invalid code pattern: {str(e)}")
                raise ValueError(f"Invalid code pattern: {str(e)}")

    def validate(self, value: Any, context: Optional[Dict[str, Any]] = None) -> bool:
        """Validate code value."""
        if value is None:
            self.add_error("Code value cannot be None", "null_value")
            return False
            
        str_value = str(value).strip()
        if not str_value:
            self.add_error("Code value cannot be empty", "empty_value")
            return False
            
        check_value = str_value if self._case_sensitive else str_value.upper()
        
        # Check exact matches
        if check_value in self._valid_codes:
            return True
            
        # Check patterns if allowed
        if self._allow_pattern:
            for pattern in self._patterns:
                if pattern.match(str_value):
                    return True
                    
        self.add_error(
            f"Invalid code value: {value}",
            "invalid_code",
            {
                'value': value,
                'case_sensitive': self._case_sensitive,
                'pattern_match': self._allow_pattern
            }
        )
        return False

class CompositeValidator(BaseValidator, IFieldValidator):
    """Combines multiple validators."""
    
    def __init__(self, validators: List[IFieldValidator],
                 require_all: bool = True):
        """Initialize with list of validators."""
        super().__init__()
        if not validators:
            raise ValueError("At least one validator required")
        self._validators = validators
        self._require_all = require_all

    def validate(self, value: Any, context: Optional[Dict[str, Any]] = None) -> bool:
        """Validate using all validators."""
        results = []
        
        for validator in self._validators:
            is_valid = validator.validate(value, context)
            results.append(is_valid)
            
            if is_valid and not self._require_all:
                return True
            elif not is_valid and self._require_all:
                self.errors.extend(validator.errors)
                return False
                
        if self._require_all:
            return True
            
        # If we get here, no validator passed and we needed at least one
        for validator in self._validators:
            self.errors.extend(validator.errors)
        return False