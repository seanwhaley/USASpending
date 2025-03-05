"""Tests for base validation functionality."""
import pytest
from unittest.mock import Mock, patch
import time
from typing import Dict, Any, Optional

from usaspending.validation_base import BaseValidator
from usaspending.exceptions import ValidationError

class TestValidator(BaseValidator):
    """Test validator implementation."""
    def _validate_field_value(self, field_name: str, value: Any,
                            validation_context: Optional[Dict[str, Any]] = None) -> bool:
        """Test validation implementation."""
        # Validate based on simple rules for testing
        if field_name == 'required_field' and not value:
            self.errors.append("Required field cannot be empty")
            return False
        elif field_name == 'numeric_field' and not isinstance(value, (int, float)):
            self.errors.append("Numeric field must be a number")
            return False
        return True

@pytest.fixture
def validator():
    """Create test validator instance."""
    return TestValidator()

def test_validate_field_success(validator):
    """Test successful field validation."""
    assert validator.validate_field('test_field', 'value')
    assert not validator.errors
    
    stats = validator.get_validation_stats()
    assert stats['cache_misses'] == 1
    assert stats['validated_fields'] == 1
    assert stats['error_count'] == 0

def test_validate_field_failure(validator):
    """Test field validation failure."""
    assert not validator.validate_field('required_field', '')
    assert len(validator.errors) == 1
    assert "Required field cannot be empty" in validator.errors[0]
    
    stats = validator.get_validation_stats()
    assert stats['cache_misses'] == 1
    assert stats['error_count'] == 1

def test_validation_caching(validator):
    """Test validation result caching."""
    # First validation should miss cache
    validator.validate_field('test_field', 'value')
    initial_stats = validator.get_validation_stats()
    
    # Second validation should hit cache
    validator.validate_field('test_field', 'value')
    final_stats = validator.get_validation_stats()
    
    assert final_stats['cache_hits'] == initial_stats['cache_hits'] + 1
    assert final_stats['cache_misses'] == initial_stats['cache_misses']

def test_validation_context_affects_cache_key(validator):
    """Test that different contexts result in different cache entries."""
    context1 = {'user': 'test1'}
    context2 = {'user': 'test2'}
    
    validator.validate_field('test_field', 'value', context1)
    validator.validate_field('test_field', 'value', context2)
    
    stats = validator.get_validation_stats()
    assert stats['cache_misses'] == 2  # Should miss cache both times

def test_adapter_registration(validator):
    """Test schema adapter registration and lookup."""
    mock_adapter = Mock()
    validator.register_adapter('test_field', mock_adapter)
    
    assert validator._get_adapter('test_field') == mock_adapter
    assert validator._get_adapter('unknown_field') is None

def test_pattern_matching_adapter(validator):
    """Test pattern matching for adapter lookup."""
    mock_adapter = Mock()
    validator.register_adapter('test_*', mock_adapter)
    
    assert validator._get_adapter('test_field') == mock_adapter
    assert validator._get_adapter('test_another') == mock_adapter
    assert validator._get_adapter('other_field') is None

def test_clear_cache(validator):
    """Test cache clearing."""
    validator.validate_field('test_field', 'value')
    initial_stats = validator.get_validation_stats()
    
    validator.clear_cache()
    
    validator.validate_field('test_field', 'value')
    final_stats = validator.get_validation_stats()
    
    assert len(validator.validation_cache) == 1
    assert final_stats['cache_hits'] == 0
    assert final_stats['cache_misses'] == 1

def test_validation_stats(validator):
    """Test validation statistics tracking."""
    validator.validate_field('field1', 'value1')  # Cache miss
    validator.validate_field('field1', 'value1')  # Cache hit
    validator.validate_field('field2', 'value2')  # Cache miss
    validator.validate_field('required_field', '')  # Cache miss + error
    
    stats = validator.get_validation_stats()
    assert stats['cache_hits'] == 1
    assert stats['cache_misses'] == 3
    assert stats['validated_fields'] == 3
    assert stats['error_count'] == 1
    assert stats['cache_size'] == 3

def test_numeric_field_validation(validator):
    """Test numeric field validation."""
    assert validator.validate_field('numeric_field', 42)
    assert validator.validate_field('numeric_field', 3.14)
    assert not validator.validate_field('numeric_field', 'not a number')
    
    assert len([e for e in validator.errors if "must be a number" in e]) == 1

def test_error_accumulation(validator):
    """Test that errors accumulate across validations."""
    validator.validate_field('required_field', '')
    validator.validate_field('numeric_field', 'not a number')
    
    errors = validator.get_validation_errors()
    assert len(errors) == 2
    assert any("Required field" in e for e in errors)
    assert any("must be a number" in e for e in errors)

def test_cache_key_generation(validator):
    """Test cache key generation."""
    key1 = validator._get_cache_key('field', 'value', {'ctx': 1})
    key2 = validator._get_cache_key('field', 'value', {'ctx': 2})
    key3 = validator._get_cache_key('field', 'value', {'ctx': 1})
    
    assert key1 != key2  # Different context should produce different keys
    assert key1 == key3  # Same context should produce same key