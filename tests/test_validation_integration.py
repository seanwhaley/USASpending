"""Integration tests for validation system."""
import pytest
from typing import Dict, Any, Optional
import yaml
from pathlib import Path

from usaspending.config_provider import ConfigurationProvider
from usaspending.validation_mediator import ValidationMediator
from usaspending.validation_service import ValidationService
from usaspending.validation_base import BaseValidator
from usaspending.exceptions import ValidationError

class TestFieldValidator(BaseValidator):
    """Field validator implementation for testing."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__()
        self._config = config
        self._validation_types = config.get('validation_types', {})
        self._field_types = config.get('field_types', {})
        self.validation_cache: Dict[str, Dict[str, Any]] = {'default': {}}
    
    def _validate_field_value(self, field_name: str, value: Any,
                            validation_context: Optional[Dict[str, Any]] = None) -> bool:
        """Validate field value using configured rules."""
        field_type = self._get_field_type(field_name)
        if not field_type:
            return True
            
        rules = self._validation_types.get(field_type, [])
        return self._validate_rules(value, rules)
    
    def _get_field_type(self, field_name: str) -> Optional[str]:
        """Get field type from configuration."""
        if field_name in self._field_types:
            return str(self._field_types[field_name])
            
        # Check pattern matches
        import re
        for pattern, type_name in self._field_types.items():
            if '*' in pattern:
                regex = pattern.replace('*', '.*')
                if re.match(regex, field_name):
                    return str(type_name)
                    
        return None

    def _validate_rules(self, value: Any, rules: list[Dict[str, Any]]) -> bool:
        """Apply validation rules to a value."""
        for rule in rules:
            if not self._validate_rule(value, rule):
                return False
        return True

    def _validate_rule(self, value: Any, rule: Dict[str, Any]) -> bool:
        """Validate a single rule."""
        # Implementation would go here - for test purposes always return True
        return True


@pytest.fixture
def field_validator(valid_config: Dict[str, Any]) -> TestFieldValidator:
    """Create field validator instance."""
    return TestFieldValidator(valid_config)


@pytest.fixture
def validation_mediator(field_validator: TestFieldValidator) -> ValidationMediator:
    """Create validation mediator instance."""
    return ValidationMediator(field_validator)


@pytest.fixture
def validation_service(validation_mediator: ValidationMediator, 
                      valid_config: Dict[str, Any]) -> ValidationService:
    """Create validation service instance."""
    return ValidationService(validation_mediator, valid_config)


def test_contract_validation_success(validation_service: ValidationService) -> None:
    """Test successful contract validation."""
    data = {
        'contract_number': 'C123456',
        'award_amount': 50000,
        'award_date': '2024-01-01',
        'description': 'Test contract',
        'vendor_name': 'Test Vendor Inc'
    }
    
    assert validation_service.validate_entity('contract', data) is True
    assert len(validation_service.get_validation_errors()) == 0


def test_contract_validation_failure(validation_service: ValidationService) -> None:
    """Test contract validation failure."""
    # Invalid contract number format
    data = {
        'contract_number': 'invalid-123',  # Contains invalid characters
        'award_amount': 50000,
        'award_date': '2024-01-01'
    }
    
    assert validation_service.validate_entity('contract', data) is False
    assert len(validation_service.get_validation_errors()) > 0
    
    # Missing required field
    data = {
        'contract_number': 'C123456',
        'award_date': '2024-01-01'
        # Missing award_amount
    }
    
    assert validation_service.validate_entity('contract', data) is False
    assert len(validation_service.get_validation_errors()) > 0


def test_date_dependency_validation(validation_service: ValidationService) -> None:
    """Test date dependency validation."""
    # Valid date range
    data = {
        'contract_number': 'C123456',
        'award_amount': 50000,
        'award_date': '2024-01-01',
        'modification_date': '2024-06-01'
    }
    
    assert validation_service.validate_entity('contract', data) is True
    
    # Invalid date range (modification before award)
    data['modification_date'] = '2023-12-31'
    assert validation_service.validate_field('modification_date', data['modification_date'],
                                          {'record': data}) is False


def test_amount_dependency_validation(validation_service: ValidationService) -> None:
    """Test amount dependency validation."""
    # Valid amount relationship
    data = {
        'contract_number': 'C123456',
        'award_amount': 50000,
        'sub_award_amount': 25000
    }
    
    assert validation_service.validate_field('sub_award_amount', data['sub_award_amount'],
                                          {'record': data}) is True
    
    # Invalid amount (sub-award greater than award)
    data['sub_award_amount'] = 75000
    assert validation_service.validate_field('sub_award_amount', data['sub_award_amount'],
                                          {'record': data}) is False


def test_pattern_field_validation(validation_service: ValidationService) -> None:
    """Test pattern-based field validation."""
    # Test agency code format
    assert validation_service.validate_field('agency_code', 'AG123') is True
    assert validation_service.validate_field('agency_code', 'invalid-123') is False
    
    # Test dynamic pattern matching
    assert validation_service.validate_field('reference_code', 'REF123') is True  # matches code_*
    assert validation_service.validate_field('program_amount', 500) is True  # matches *_amount
    assert validation_service.validate_field('completion_date', '2024-12-31') is True  # matches *_date


def test_validation_with_context(validation_service: ValidationService) -> None:
    """Test validation with different contexts."""
    # Contract context
    context = {'entity_type': 'contract'}
    assert validation_service.validate_field('contract_number', 'C123456', context) is True
    assert validation_service.validate_field('description', 'Test contract', context) is True
    
    # Agency context
    context = {'entity_type': 'agency'}
    assert validation_service.validate_field('agency_code', 'AG123', context) is True
    assert validation_service.validate_field('agency_name', 'Test Agency', context) is True


def test_complex_validation_scenario(validation_service: ValidationService) -> None:
    """Test complex validation scenario with multiple dependencies."""
    data = {
        'contract_number': 'C123456',
        'award_amount': 100000,
        'award_date': '2024-01-01',
        'modification_date': '2024-06-01',
        'sub_award_amount': 50000,
        'agency_code': 'AG123',
        'vendor_name': 'Test Vendor Inc',
        'description': 'Complex test contract'
    }
    
    # Initial validation should succeed
    assert validation_service.validate_entity('contract', data) is True
    
    # Modify data to create invalid state
    data['modification_date'] = '2023-12-31'  # Before award date
    data['sub_award_amount'] = 150000  # Greater than award amount
    data['agency_code'] = 'invalid'  # Invalid format
    
    assert validation_service.validate_entity('contract', data) is False
    errors = validation_service.get_validation_errors()
    assert len(errors) > 0
    
    # Verify specific error conditions
    error_text = ' '.join(errors).lower()
    assert any('date' in err.lower() for err in errors)  # Date dependency error
    assert any('amount' in err.lower() for err in errors)  # Amount dependency error
    assert any('code' in err.lower() for err in errors)  # Format error


def test_validation_error_collection(validation_service: ValidationService) -> None:
    """Test collection and formatting of validation errors."""
    data = {
        'contract_number': 'invalid-123',
        'award_amount': -1000,
        'award_date': 'invalid-date',
        'agency_code': '123'
    }
    
    assert validation_service.validate_entity('contract', data) is False
    errors = validation_service.get_validation_errors()
    
    # Verify error details
    assert len(errors) > 0
    assert any('contract_number' in err.lower() for err in errors)
    assert any('amount' in err.lower() for err in errors)
    assert any('date' in err.lower() for err in errors)