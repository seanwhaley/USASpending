"""Tests for validation service functionality."""
import pytest
from unittest.mock import Mock, patch
from typing import Dict, Any, Optional

from usaspending.validation_service import ValidationService
from usaspending.validation_rules import ValidationRuleLoader
from usaspending.exceptions import ValidationError

@pytest.fixture
def mock_rule_loader():
    """Create mock validation rule loader."""
    loader = Mock(spec=ValidationRuleLoader)
    loader.get_field_rules.return_value = {
        'type': 'string',
        'required': True,
        'min_length': 3
    }
    return loader

@pytest.fixture
def validation_service(mock_rule_loader):
    """Create validation service instance."""
    return ValidationService(mock_rule_loader)

@pytest.fixture
def mock_adapter():
    """Create mock field adapter."""
    adapter = Mock()
    adapter.validate.return_value = True
    adapter.get_errors.return_value = []
    return adapter

def test_validation_service_initialization(validation_service, mock_rule_loader):
    """Test validation service initialization."""
    assert validation_service.rule_loader == mock_rule_loader
    assert isinstance(validation_service._rule_cache, dict)
    assert isinstance(validation_service._required_fields, set)

def test_validate_field_with_rules(validation_service, mock_adapter):
    """Test field validation with rules."""
    validation_service.register_adapter('test_field', mock_adapter)
    
    assert validation_service.validate_field('test_field', 'valid value')
    mock_adapter.validate.assert_called_once()
    assert not validation_service.get_validation_errors()

def test_validate_field_no_rules(validation_service, mock_rule_loader):
    """Test field validation with no rules."""
    mock_rule_loader.get_field_rules.return_value = None
    
    assert validation_service.validate_field('unknown_field', 'value')
    assert not validation_service.get_validation_errors()

def test_validate_required_field_empty(validation_service, mock_adapter):
    """Test validation of empty required field."""
    validation_service.register_adapter('test_field', mock_adapter)
    
    assert not validation_service.validate_field('test_field', '')
    errors = validation_service.get_validation_errors()
    assert len(errors) == 1
    assert "Required field" in errors[0]

def test_validation_with_context(validation_service, mock_adapter):
    """Test validation with context data."""
    validation_service.register_adapter('test_field', mock_adapter)
    context = {'user': 'test_user'}
    
    validation_service.validate_field('test_field', 'value', context)
    mock_adapter.validate.assert_called_with('value', {'type': 'string', 'required': True, 'min_length': 3}, context)

def test_validation_caching(validation_service, mock_adapter):
    """Test validation result caching."""
    validation_service.register_adapter('test_field', mock_adapter)
    
    # First validation - should miss cache
    validation_service.validate_field('test_field', 'value')
    initial_stats = validation_service.get_validation_stats()
    
    # Second validation - should hit cache
    validation_service.validate_field('test_field', 'value')
    final_stats = validation_service.get_validation_stats()
    
    assert final_stats['cache_hits'] == initial_stats['cache_hits'] + 1
    assert final_stats['cache_misses'] == initial_stats['cache_misses']

def test_rule_caching(validation_service, mock_rule_loader):
    """Test validation rule caching."""
    # First call should query loader
    validation_service._get_field_rules('test_field')
    mock_rule_loader.get_field_rules.assert_called_once()
    
    # Second call should use cache
    validation_service._get_field_rules('test_field')
    mock_rule_loader.get_field_rules.assert_called_once()

def test_adapter_error_handling(validation_service, mock_adapter):
    """Test adapter error handling."""
    mock_adapter.validate.side_effect = Exception('Validation error')
    validation_service.register_adapter('test_field', mock_adapter)
    
    assert not validation_service.validate_field('test_field', 'value')
    errors = validation_service.get_validation_errors()
    assert len(errors) == 1
    assert 'Validation error' in errors[0]

def test_required_field_tracking(validation_service, mock_adapter):
    """Test required field tracking."""
    validation_service.register_adapter('required_field', mock_adapter)
    validation_service.validate_field('required_field', 'value')
    
    stats = validation_service.get_validation_stats()
    assert stats['required_fields'] == 1

def test_clear_caches(validation_service, mock_adapter):
    """Test clearing all validation caches."""
    validation_service.register_adapter('test_field', mock_adapter)
    
    # Add some data to caches
    validation_service.validate_field('test_field', 'value')
    validation_service._get_field_rules('test_field')
    
    validation_service.clear_caches()
    
    assert len(validation_service._rule_cache) == 0
    assert len(validation_service._required_fields) == 0
    assert len(validation_service.validation_cache) == 0

def test_validation_with_different_contexts(validation_service, mock_adapter):
    """Test validation with different contexts."""
    validation_service.register_adapter('test_field', mock_adapter)
    
    context1 = {'user': 'user1'}
    context2 = {'user': 'user2'}
    
    validation_service.validate_field('test_field', 'value', context1)
    validation_service.validate_field('test_field', 'value', context2)
    
    stats = validation_service.get_validation_stats()
    assert stats['cache_misses'] == 2  # Different contexts should be cached separately

def test_extended_validation_stats(validation_service, mock_adapter):
    """Test extended validation statistics."""
    validation_service.register_adapter('test_field', mock_adapter)
    
    # Generate some validation activity
    validation_service.validate_field('test_field', 'value1')
    validation_service.validate_field('test_field', 'value1')  # Cache hit
    validation_service.validate_field('test_field', 'value2')  # Different value
    
    stats = validation_service.get_validation_stats()
    assert 'required_fields' in stats
    assert 'rule_cache_size' in stats
    assert 'cache_hits' in stats
    assert 'cache_misses' in stats
    assert 'validated_fields' in stats
    assert 'error_count' in stats

def test_rule_loader_error_handling(validation_service, mock_rule_loader):
    """Test handling of rule loader errors."""
    mock_rule_loader.get_field_rules.side_effect = Exception('Rule loading failed')
    
    # Should not raise exception, but return None for rules
    rules = validation_service._get_field_rules('test_field')
    assert rules is None