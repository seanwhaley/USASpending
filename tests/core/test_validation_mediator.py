import pytest
from typing import Dict, Any, List
from usaspending.core.validation_mediator import ValidationMediator
from usaspending.core.types import ValidationRule, RuleType, ValidationSeverity
from usaspending.core.validation import RuleSet

@pytest.fixture
def mediator():
    return ValidationMediator()

@pytest.fixture
def sample_rule_sets():
    personal_rules = [
        ValidationRule(
            rule_type=RuleType.REQUIRED,
            field_name='name',
            parameters={},
            message='Name is required',
            enabled=True,
            severity=ValidationSeverity.ERROR
        ),
        ValidationRule(
            rule_type=RuleType.PATTERN,
            field_name='email',
            parameters={'pattern': r'^[\w\.-]+@[\w\.-]+\.\w+$'},
            message='Invalid email format',
            enabled=True,
            severity=ValidationSeverity.ERROR
        )
    ]
    
    address_rules = [
        ValidationRule(
            rule_type=RuleType.REQUIRED,
            field_name='street',
            parameters={},
            message='Street is required',
            enabled=True,
            severity=ValidationSeverity.ERROR
        ),
        ValidationRule(
            rule_type=RuleType.PATTERN,
            field_name='postal_code',
            parameters={'pattern': r'^\d{5}(?:-\d{4})?$'},
            message='Invalid postal code format',
            enabled=True,
            severity=ValidationSeverity.WARNING
        )
    ]
    
    return {
        'personal': RuleSet('personal', personal_rules),
        'address': RuleSet('address', address_rules)
    }

def test_mediator_initialization(mediator):
    assert len(mediator._rule_sets) == 0
    assert len(mediator._errors) == 0

def test_register_rules(mediator, sample_rule_sets):
    personal_rules = sample_rule_sets['personal'].rules
    mediator.register_rules('personal', personal_rules)
    
    assert 'personal' in mediator._rule_sets
    assert len(mediator._rule_sets['personal'].rules) == len(personal_rules)

def test_register_rule_set(mediator, sample_rule_sets):
    rule_set = sample_rule_sets['address']
    mediator.register_rule_set(rule_set)
    
    assert rule_set.name in mediator._rule_sets
    assert mediator._rule_sets[rule_set.name] == rule_set

def test_validate_entity_with_single_rule_set(mediator, sample_rule_sets):
    mediator.register_rule_set(sample_rule_sets['personal'])
    
    # Test valid data
    valid_data = {
        'name': 'John Doe',
        'email': 'john@example.com'
    }
    assert mediator.validate_entity('test', valid_data)
    assert len(mediator.get_validation_errors()) == 0
    
    # Test invalid data
    invalid_data = {
        'name': '',
        'email': 'invalid-email'
    }
    assert not mediator.validate_entity('test', invalid_data)
    errors = mediator.get_validation_errors()
    assert len(errors) == 2

def test_validate_entity_with_multiple_rule_sets(mediator, sample_rule_sets):
    # Register both rule sets
    for rule_set in sample_rule_sets.values():
        mediator.register_rule_set(rule_set)
    
    # Test valid data for both rule sets
    valid_data = {
        'name': 'John Doe',
        'email': 'john@example.com',
        'street': '123 Main St',
        'postal_code': '12345-6789'
    }
    assert mediator.validate_entity('test', valid_data)
    assert len(mediator.get_validation_errors()) == 0

def test_validate_entity_with_context(mediator, sample_rule_sets):
    mediator.register_rule_set(sample_rule_sets['personal'])
    
    context = {
        'rule_set': 'personal',  # Only validate against personal rules
        'strict_mode': True
    }
    
    # Should pass personal validation but missing address fields
    data = {
        'name': 'John Doe',
        'email': 'john@example.com'
    }
    assert mediator.validate_entity('test', data, context)

def test_validate_with_disabled_rule_set(mediator, sample_rule_sets):
    # Create a disabled rule set
    rules = [
        ValidationRule(
            rule_type=RuleType.REQUIRED,
            field_name='optional_field',
            parameters={},
            message='This should not be validated',
            enabled=True
        )
    ]
    disabled_set = RuleSet('disabled_set', rules, enabled=False)
    mediator.register_rule_set(disabled_set)
    
    # Should pass validation since rule set is disabled
    data = {}  # Missing required field
    assert mediator.validate_entity('test', data)

def test_error_collection_across_rule_sets(mediator, sample_rule_sets):
    # Register both rule sets
    for rule_set in sample_rule_sets.values():
        mediator.register_rule_set(rule_set)
    
    # Create data with errors in both rule sets
    invalid_data = {
        'name': '',  # Error in personal
        'email': 'john@example.com',
        'street': '',  # Error in address
        'postal_code': 'invalid'  # Error in address
    }
    
    assert not mediator.validate_entity('test', invalid_data)
    errors = mediator.get_validation_errors()
    assert len(errors) == 3  # Should have errors from both rule sets

def test_clear_errors(mediator, sample_rule_sets):
    mediator.register_rule_set(sample_rule_sets['personal'])
    
    # Generate some errors
    mediator.validate_entity('test', {'name': '', 'email': 'invalid'})
    assert len(mediator.get_validation_errors()) > 0
    
    # Clear errors
    mediator.clear_errors()
    assert len(mediator.get_validation_errors()) == 0

def test_severity_levels(mediator):
    # Create rules with different severity levels
    rules = [
        ValidationRule(
            rule_type=RuleType.REQUIRED,
            field_name='critical_field',
            parameters={},
            message='Critical error',
            enabled=True,
            severity=ValidationSeverity.ERROR
        ),
        ValidationRule(
            rule_type=RuleType.PATTERN,
            field_name='warning_field',
            parameters={'pattern': r'\d+'},
            message='Warning message',
            enabled=True,
            severity=ValidationSeverity.WARNING
        )
    ]
    mediator.register_rules('mixed_severity', rules)
    
    # Test data that triggers both rules
    data = {
        'critical_field': '',
        'warning_field': 'abc'
    }
    
    assert not mediator.validate_entity('test', data)
    errors = mediator.get_validation_errors()
    assert any(ValidationSeverity.ERROR.value in e for e in errors)
    assert any(ValidationSeverity.WARNING.value in e for e in errors)