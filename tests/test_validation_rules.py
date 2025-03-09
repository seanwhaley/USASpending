"""Tests for validation rules implementation."""
import pytest
from typing import Dict, Any, Optional, List, Generator
import re
from datetime import datetime

from usaspending.validation_base import BaseValidator


class TestValidator(BaseValidator):
    """Test validator implementation."""
    
    def __init__(self) -> None:
        super().__init__()
        self._rules: Dict[str, Any] = {}
        self.validation_cache: Dict[str, Dict[str, Any]] = {'default': {}}  # Initialize with proper structure
        self._cache_hits: int = 0
        self._cache_misses: int = 0
    
    def set_rules(self, rules: Dict[str, Any]) -> None:
        """Set validation rules for testing."""
        self._rules = rules
    
    def _validate_field_value(self, field_name: str, value: Any,
                            validation_context: Optional[Dict[str, Any]] = None) -> bool:
        """Implement basic rule validation for testing."""
        if field_name not in self._rules:
            return True
            
        rule = self._rules[field_name]
        return self._apply_rule(value, rule)
    
    def _apply_rule(self, value: Any, rule: Dict[str, Any]) -> bool:
        """Apply validation rule."""
        rule_type = rule.get('type')
        
        if rule_type == 'required':
            if value is None or (isinstance(value, str) and not value.strip()):
                self.errors.append('Field is required')
                return False
                
        elif rule_type == 'pattern':
            pattern = rule.get('pattern')
            if pattern and not re.match(pattern, str(value)):
                self.errors.append('Invalid pattern')
                return False
                
        elif rule_type == 'range':
            try:
                num_value = float(value)
                min_val = rule.get('min')
                max_val = rule.get('max')
                
                if min_val is not None and num_value < min_val:
                    self.errors.append(f'Value below minimum {min_val}')
                    return False
                    
                if max_val is not None and num_value > max_val:
                    self.errors.append(f'Value above maximum {max_val}')
                    return False
                    
            except (ValueError, TypeError):
                self.errors.append('Invalid numeric value')
                return False
                
        elif rule_type == 'date':
            try:
                if isinstance(value, str):
                    datetime.strptime(value, rule.get('format', '%Y-%m-%d'))
                return True
            except ValueError:
                self.errors.append('Invalid date format')
                return False
                
        elif rule_type == 'enum':
            allowed = rule.get('values', [])
            if str(value).upper() not in (str(v).upper() for v in allowed):
                self.errors.append('Invalid enum value')
                return False
                
        return True

    def get_validation_stats(self) -> Dict[str, int]:
        """Get validation statistics."""
        return {
            'cache_hits': self._cache_hits,
            'cache_misses': self._cache_misses,
            'validated_fields': len(self._rules),
            'error_count': len(self.errors),
            'cache_size': len(self.validation_cache)
        }

    def clear_cache(self) -> None:
        """Clear validation cache."""
        self.validation_cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0


@pytest.fixture
def validator() -> TestValidator:
    """Create test validator instance."""
    return TestValidator()


def test_required_rule(validator: TestValidator) -> None:
    """Test required value validation."""
    validator.set_rules({'test_field': {'type': 'required'}})
    
    # Valid values
    assert validator.validate_field('test_field', 'value') is True
    assert validator.validate_field('test_field', 0) is True
    assert validator.validate_field('test_field', False) is True
    
    # Invalid values
    assert validator.validate_field('test_field', None) is False
    assert validator.validate_field('test_field', '') is False
    assert validator.validate_field('test_field', '   ') is False
    assert 'required' in validator.get_validation_errors()[0].lower()


def test_pattern_rule(validator: TestValidator) -> None:
    """Test pattern validation."""
    validator.set_rules({
        'test_field': {
            'type': 'pattern',
            'pattern': r'^[A-Z]{2}\d{3}$'  # Format: Two uppercase letters followed by 3 digits
        }
    })
    
    # Valid values
    assert validator.validate_field('test_field', 'AB123') is True
    assert validator.validate_field('test_field', 'XY999') is True
    
    # Invalid values
    assert validator.validate_field('test_field', 'abc123') is False
    assert validator.validate_field('test_field', 'AB12') is False
    assert validator.validate_field('test_field', '12ABC') is False
    assert 'pattern' in validator.get_validation_errors()[0].lower()


def test_range_rule(validator: TestValidator) -> None:
    """Test numeric range validation."""
    validator.set_rules({
        'test_field': {
            'type': 'range',
            'min': 0,
            'max': 100
        }
    })
    
    # Valid values
    assert validator.validate_field('test_field', 0) is True
    assert validator.validate_field('test_field', 50) is True
    assert validator.validate_field('test_field', 100) is True
    assert validator.validate_field('test_field', '75.5') is True
    
    # Invalid values
    assert validator.validate_field('test_field', -1) is False
    assert validator.validate_field('test_field', 101) is False
    assert validator.validate_field('test_field', 'abc') is False
    assert any('minimum' in err.lower() or 'maximum' in err.lower() or 'numeric' in err.lower() 
              for err in validator.get_validation_errors())


def test_date_rule(validator: TestValidator) -> None:
    """Test date format validation."""
    validator.set_rules({
        'test_field': {
            'type': 'date',
            'format': '%Y-%m-%d'
        }
    })
    
    # Valid values
    assert validator.validate_field('test_field', '2024-01-01') is True
    assert validator.validate_field('test_field', '2023-12-31') is True
    
    # Invalid values
    assert validator.validate_field('test_field', '01-01-2024') is False
    assert validator.validate_field('test_field', '2024/01/01') is False
    assert validator.validate_field('test_field', 'invalid') is False
    assert 'date' in validator.get_validation_errors()[0].lower()


def test_enum_rule(validator: TestValidator) -> None:
    """Test enum value validation."""
    validator.set_rules({
        'test_field': {
            'type': 'enum',
            'values': ['ACTIVE', 'INACTIVE', 'PENDING']
        }
    })
    
    # Valid values (case-insensitive)
    assert validator.validate_field('test_field', 'ACTIVE') is True
    assert validator.validate_field('test_field', 'inactive') is True
    assert validator.validate_field('test_field', 'Pending') is True
    
    # Invalid values
    assert validator.validate_field('test_field', 'UNKNOWN') is False
    assert validator.validate_field('test_field', '') is False
    assert validator.validate_field('test_field', None) is False
    assert 'enum' in validator.get_validation_errors()[0].lower()


def test_validation_caching(validator: TestValidator) -> None:
    """Test validation result caching."""
    validator.set_rules({
        'test_field': {
            'type': 'pattern',
            'pattern': r'\d+'
        }
    })
    
    # First validation
    assert validator.validate_field('test_field', '123') is True
    initial_cache_misses = validator._cache_misses
    
    # Repeat validation with same value
    assert validator.validate_field('test_field', '123') is True
    assert validator._cache_hits > 0
    assert validator._cache_misses == initial_cache_misses  # No new cache misses
    
    # Different value should miss cache
    assert validator.validate_field('test_field', '456') is True
    assert validator._cache_misses > initial_cache_misses


def test_validation_context(validator: TestValidator) -> None:
    """Test validation with context."""
    validator.set_rules({
        'test_field': {
            'type': 'pattern',
            'pattern': r'\d+'
        }
    })
    
    # Same value, different contexts should not hit cache
    context1: Dict[str, Any] = {'entity_type': 'type1'}
    context2: Dict[str, Any] = {'entity_type': 'type2'}
    
    validator.validate_field('test_field', '123', context1)
    initial_cache_misses = validator._cache_misses
    
    validator.validate_field('test_field', '123', context2)
    assert validator._cache_misses > initial_cache_misses


def test_validation_stats(validator: TestValidator) -> None:
    """Test validation statistics."""
    validator.set_rules({
        'test_field': {
            'type': 'pattern',
            'pattern': r'\d+'
        }
    })
    
    # Perform some validations
    validator.validate_field('test_field', '123')  # Valid
    validator.validate_field('test_field', '123')  # Cache hit
    validator.validate_field('test_field', 'abc')  # Invalid
    
    stats = validator.get_validation_stats()
    assert stats['cache_hits'] > 0
    assert stats['cache_misses'] > 0
    assert stats['validated_fields'] == 1  # Unique fields
    assert stats['error_count'] > 0
    assert stats['cache_size'] > 0


def test_clear_cache(validator: TestValidator) -> None:
    """Test cache clearing."""
    validator.set_rules({
        'test_field': {
            'type': 'pattern',
            'pattern': r'\d+'
        }
    })
    
    # Populate cache
    validator.validate_field('test_field', '123')
    assert len(validator.validation_cache) > 0
    
    # Clear cache
    validator.clear_cache()
    assert len(validator.validation_cache) == 0
    assert validator._cache_hits == 0
    assert validator._cache_misses == 0