"""Tests for validation service functionality."""
import pytest
from typing import Dict, Any, Optional, List
from unittest.mock import Mock, patch

from usaspending.validation_service import ValidationService
from usaspending.interfaces import IValidationMediator


class MockValidationMediator(IValidationMediator):
    """Mock validation mediator for testing."""
    
    def __init__(self, should_validate: bool = True):
        self._should_validate = should_validate
        self._errors: List[str] = []
        self._last_context: Optional[Dict[str, Any]] = None
    
    def validate_entity(self, entity_type: str, data: Dict[str, Any]) -> bool:
        if not self._should_validate:
            self._errors.append(f"Entity validation failed for {entity_type}")
            return False
        return True
    
    def validate_field(self, field_name: str, value: Any, entity_type: Optional[str] = None) -> bool:
        self._last_context = {'field': field_name, 'value': value, 'entity_type': entity_type}
        if not self._should_validate:
            self._errors.append(f"Field validation failed for {field_name}")
            return False
        return True
    
    def get_validation_errors(self) -> List[str]:
        return self._errors.copy()


@pytest.fixture
def valid_config():
    """Create valid test configuration."""
    return {
        'validation_types': {
            'string': [
                {'type': 'pattern', 'pattern': '[A-Za-z]+'},
                {'type': 'length', 'min': 1, 'max': 100}
            ],
            'number': [
                {'type': 'range', 'min': 0, 'max': 1000}
            ]
        },
        'field_types': {
            'name': 'string',
            'amount': 'number',
            'code_*': 'string'
        },
        'field_dependencies': {
            'end_date': {
                'fields': ['start_date'],
                'validation': {
                    'type': 'date_range',
                    'min_field': 'start_date'
                }
            },
            'sub_amount': {
                'fields': ['total_amount'],
                'validation': {
                    'type': 'range',
                    'max_field': 'total_amount'
                }
            }
        }
    }


@pytest.fixture
def mock_mediator():
    """Create validation mediator mock."""
    return MockValidationMediator()


@pytest.fixture
def validation_service(valid_config, mock_mediator):
    """Create validation service instance."""
    return ValidationService(mock_mediator, valid_config)


def test_validation_service_initialization(validation_service, mock_mediator, valid_config):
    """Test service initialization."""
    assert validation_service._mediator == mock_mediator
    assert validation_service._config == valid_config
    assert len(validation_service._rules) > 0
    assert len(validation_service._dependencies) > 0


def test_load_validation_rules(validation_service, valid_config):
    """Test validation rules loading."""
    rules = validation_service._rules
    
    assert 'string' in rules
    assert 'number' in rules
    assert len(rules['string']) == 2  # pattern and length rules
    assert len(rules['number']) == 1  # range rule
    
    # Verify rule structure
    string_rules = rules['string']
    assert any(r['type'] == 'pattern' for r in string_rules)
    assert any(r['type'] == 'length' for r in string_rules)


def test_initialize_dependencies(validation_service, valid_config):
    """Test dependency initialization."""
    deps = validation_service._dependencies
    
    assert 'end_date' in deps
    assert 'sub_amount' in deps
    assert 'start_date' in deps['end_date']
    assert 'total_amount' in deps['sub_amount']


def test_get_field_type(validation_service):
    """Test field type determination."""
    # Direct match
    assert validation_service._get_field_type('name') == 'string'
    assert validation_service._get_field_type('amount') == 'number'
    
    # Pattern match
    assert validation_service._get_field_type('code_123') == 'string'
    assert validation_service._get_field_type('code_abc') == 'string'
    
    # No match
    assert validation_service._get_field_type('unknown_field') is None


def test_validate_entity_success(validation_service):
    """Test successful entity validation."""
    data = {
        'name': 'test',
        'amount': 500
    }
    
    assert validation_service.validate_entity('test_entity', data) is True
    assert len(validation_service.get_validation_errors()) == 0


def test_validate_entity_failure(validation_service, mock_mediator):
    """Test entity validation failure."""
    # Configure mediator to fail validation
    mock_mediator._should_validate = False
    
    data = {'name': 'test'}
    assert validation_service.validate_entity('test_entity', data) is False
    assert len(validation_service.get_validation_errors()) > 0


def test_dependency_validation(validation_service):
    """Test validation with dependencies."""
    # Test valid dependency chain
    data = {
        'start_date': '2024-01-01',
        'end_date': '2024-12-31',
        'total_amount': 1000,
        'sub_amount': 500
    }
    context = {'record': data}
    
    assert validation_service.validate_field('end_date', data['end_date'], context) is True
    assert validation_service.validate_field('sub_amount', data['sub_amount'], context) is True
    
    # Test invalid dependency (missing field)
    data = {'end_date': '2024-12-31'}  # Missing start_date
    context = {'record': data}
    
    assert validation_service.validate_field('end_date', data['end_date'], context) is False
    assert any('missing' in err.lower() for err in validation_service.get_validation_errors())


def test_apply_rules_success(validation_service):
    """Test successful rule application."""
    # Test string validation
    value = "TestString"
    rules = validation_service._rules['string']
    assert validation_service._apply_rules(value, rules) is True
    
    # Test number validation
    value = 500
    rules = validation_service._rules['number']
    assert validation_service._apply_rules(value, rules) is True


def test_apply_rules_failure(validation_service):
    """Test rule application failure."""
    # Test invalid string (contains numbers)
    value = "Test123"
    rules = validation_service._rules['string']
    assert validation_service._apply_rules(value, rules) is False
    assert len(validation_service.get_validation_errors()) > 0
    
    # Test invalid number (out of range)
    value = 1500
    rules = validation_service._rules['number']
    assert validation_service._apply_rules(value, rules) is False
    assert len(validation_service.get_validation_errors()) > 0


def test_validate_field_with_context(validation_service):
    """Test field validation with context."""
    # Test with entity type context
    context = {'entity_type': 'test_entity'}
    assert validation_service.validate_field('name', 'TestValue', context) is True
    
    # Test with record context
    context = {
        'entity_type': 'test_entity',
        'record': {'name': 'TestValue', 'related_field': 'Value'}
    }
    assert validation_service.validate_field('name', 'TestValue', context) is True


def test_error_handling(validation_service, mock_mediator):
    """Test error handling during validation."""
    # Test mediator error handling
    with patch.object(mock_mediator, 'validate_field', side_effect=Exception("Validation error")):
        assert validation_service.validate_field('test_field', 'value') is False
        assert any('validation error' in err.lower() for err in validation_service.get_validation_errors())
    
    # Test rule application error
    with patch.object(validation_service, '_apply_rules', side_effect=Exception("Rule error")):
        assert validation_service.validate_field('test_field', 'value') is False
        assert any('rule error' in err.lower() for err in validation_service.get_validation_errors())