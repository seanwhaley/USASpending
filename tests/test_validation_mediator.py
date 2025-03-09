"""Tests for validation mediator functionality."""
import pytest
from unittest.mock import Mock, patch
from typing import Dict, Any, Optional, List

from usaspending.validation_mediator import ValidationMediator
from usaspending.interfaces import IFieldValidator, IValidatable
from usaspending.exceptions import ValidationError


class MockFieldValidator(IFieldValidator):
    """Mock field validator for testing."""
    
    def __init__(self) -> None:
        self.errors: List[str] = []
    
    def validate_field(self, field_name: str, value: Any, 
                      validation_context: Optional[Dict[str, Any]] = None) -> bool:
        if value == 'invalid':
            self.errors.append(f"Invalid value for {field_name}")
            return False
        return True
    
    def get_validation_errors(self) -> List[str]:
        return self.errors


class MockValidatable(IValidatable):
    """Mock validatable entity for testing."""
    
    def __init__(self, should_validate: bool = True) -> None:
        self._should_validate = should_validate
        self._errors: List[str] = []
    
    def validate(self) -> bool:
        if not self._should_validate:
            self._errors.append("Validation failed")
            return False
        return True
    
    def get_validation_errors(self) -> List[str]:
        return self._errors


@pytest.fixture
def field_validator() -> MockFieldValidator:
    """Create field validator instance."""
    return MockFieldValidator()


@pytest.fixture
def validation_mediator(field_validator: MockFieldValidator) -> ValidationMediator:
    """Create validation mediator instance."""
    return ValidationMediator(field_validator)


def test_validation_mediator_initialization(validation_mediator: ValidationMediator, 
                                         field_validator: MockFieldValidator) -> None:
    """Test mediator initialization."""
    assert validation_mediator._field_validator == field_validator
    assert len(validation_mediator._errors) == 0
    assert len(validation_mediator._entity_validators) == 0


def test_register_entity_validator(validation_mediator: ValidationMediator) -> None:
    """Test registering entity validator."""
    validator = MockValidatable()
    validation_mediator.register_entity_validator('test_entity', validator)
    assert validation_mediator._entity_validators['test_entity'] == validator


def test_validate_entity_success(validation_mediator: ValidationMediator) -> None:
    """Test successful entity validation."""
    # Register validator
    validator = MockValidatable(should_validate=True)
    validation_mediator.register_entity_validator('test_entity', validator)
    
    # Test validation
    data = {'field1': 'value1', 'field2': 'value2'}
    assert validation_mediator.validate_entity('test_entity', data) is True
    assert len(validation_mediator.get_validation_errors()) == 0


def test_validate_entity_failure(validation_mediator: ValidationMediator) -> None:
    """Test failed entity validation."""
    # Register validator that will fail
    validator = MockValidatable(should_validate=False)
    validation_mediator.register_entity_validator('test_entity', validator)
    
    # Test validation
    data = {'field1': 'value1'}
    assert validation_mediator.validate_entity('test_entity', data) is False
    assert len(validation_mediator.get_validation_errors()) > 0


def test_validate_field_success(validation_mediator: ValidationMediator) -> None:
    """Test successful field validation."""
    assert validation_mediator.validate_field('test_field', 'valid') is True
    assert len(validation_mediator.get_validation_errors()) == 0


def test_validate_field_failure(validation_mediator: ValidationMediator) -> None:
    """Test failed field validation."""
    assert validation_mediator.validate_field('test_field', 'invalid') is False
    assert len(validation_mediator.get_validation_errors()) > 0


def test_validation_with_context(validation_mediator: ValidationMediator) -> None:
    """Test validation with entity type context."""
    assert validation_mediator.validate_field('test_field', 'valid', 'test_entity') is True
    assert validation_mediator.validate_field('test_field', 'invalid', 'test_entity') is False


def test_validation_stats(validation_mediator: ValidationMediator) -> None:
    """Test validation statistics."""
    validator = MockValidatable()
    validation_mediator.register_entity_validator('test_entity', validator)
    
    # Perform some validations
    validation_mediator.validate_field('field1', 'valid')
    validation_mediator.validate_field('field2', 'invalid')
    
    stats = validation_mediator.get_validation_stats()
    assert stats['error_count'] > 0
    assert stats['registered_validators'] == 1


def test_error_handling(validation_mediator: ValidationMediator) -> None:
    """Test error handling during validation."""
    # Test with None values
    assert validation_mediator.validate_field('test_field', None) is True
    
    # Test with invalid entity type
    data = {'field1': 'value1'}
    assert validation_mediator.validate_entity('non_existent', data) is True  # Fallback to field validation
    
    # Test with exception in validator
    with patch.object(validation_mediator._field_validator, 'validate_field', 
                     side_effect=Exception('Test error')):
        assert validation_mediator.validate_field('test_field', 'value') is False
        assert 'Test error' in str(validation_mediator.get_validation_errors())