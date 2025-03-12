import pytest
from typing import Dict, Any
from usaspending.core.validation import (
    BaseValidator,
    ValidationService,
    RuleSet,
    ValidationResult
)
from usaspending.core.types import (
    ValidationRule,
    RuleType,
    ValidationSeverity
)

class TestValidator(BaseValidator):
    """Test implementation of BaseValidator."""
    def validate(self, entity_id: str, data: Dict[str, Any], context: Dict[str, Any]) -> bool:
        if not data:
            self._errors.append("Data cannot be empty")
            return False
        return True

@pytest.fixture
def validator():
    return TestValidator()

@pytest.fixture
def validation_service():
    return ValidationService()

@pytest.fixture
def sample_rules():
    return [
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

@pytest.fixture
def sample_rule_set(sample_rules):
    return RuleSet('test_set', sample_rules)

def test_base_validator_initialization(validator):
    assert len(validator._errors) == 0

def test_validation_service_initialization(validation_service):
    assert validation_service._initialized
    assert len(validation_service._rules) == 0
    assert len(validation_service._rule_sets) == 0

def test_rule_set_creation(sample_rules):
    rule_set = RuleSet('test_set', sample_rules)
    assert rule_set.name == 'test_set'
    assert len(rule_set.rules) == len(sample_rules)
    assert rule_set.enabled

def test_rule_set_disable_enable(sample_rule_set):
    assert sample_rule_set.enabled
    
    sample_rule_set.enabled = False
    assert not sample_rule_set.enabled
    
    sample_rule_set.enabled = True
    assert sample_rule_set.enabled

def test_validation_service_register_rules(validation_service, sample_rules):
    validation_service.register_rules('test_group', sample_rules)
    assert 'test_group' in validation_service._rules
    assert len(validation_service._rules['test_group']) == len(sample_rules)

def test_validation_service_register_rule_set(validation_service, sample_rule_set):
    validation_service.register_rule_set(sample_rule_set)
    assert sample_rule_set.name in validation_service._rule_sets
    assert validation_service._rule_sets[sample_rule_set.name] == sample_rule_set

def test_validation_service_validate_success(validation_service, sample_rules):
    validation_service.register_rules('test_group', sample_rules)
    
    valid_data = {
        'name': 'John Doe',
        'email': 'john@example.com'
    }
    
    result = validation_service.validate('test', valid_data)
    assert isinstance(result, ValidationResult)
    assert result.is_valid
    assert len(result.errors) == 0

def test_validation_service_validate_failure(validation_service, sample_rules):
    validation_service.register_rules('test_group', sample_rules)
    
    invalid_data = {
        'name': '',
        'email': 'invalid-email'
    }
    
    result = validation_service.validate('test', invalid_data)
    assert isinstance(result, ValidationResult)
    assert not result.is_valid
    assert len(result.errors) == 2

def test_validation_rule_creation():
    rule = ValidationRule(
        rule_type=RuleType.RANGE,
        field_name='age',
        parameters={'min': 0, 'max': 120},
        message='Age must be between 0 and 120',
        enabled=True,
        severity=ValidationSeverity.ERROR
    )
    
    assert rule.rule_type == RuleType.RANGE
    assert rule.field_name == 'age'
    assert rule.parameters == {'min': 0, 'max': 120}
    assert rule.message == 'Age must be between 0 and 120'
    assert rule.enabled
    assert rule.severity == ValidationSeverity.ERROR

def test_validation_with_context(validation_service, sample_rules):
    validation_service.register_rules('test_group', sample_rules)
    
    context = {
        'strict_mode': True,
        'entity_type': 'user'
    }
    
    result = validation_service.validate('test', {'name': 'John'}, context)
    assert not result.is_valid  # Email is required in strict mode
    assert any('email' in err for err in result.errors)

def test_validation_rule_set_dependencies(validation_service):
    # Create dependent rule sets
    base_rules = [
        ValidationRule(
            rule_type=RuleType.REQUIRED,
            field_name='id',
            parameters={},
            message='ID is required',
            enabled=True
        )
    ]
    
    dependent_rules = [
        ValidationRule(
            rule_type=RuleType.PATTERN,
            field_name='id',
            parameters={'pattern': r'^\d+$'},
            message='ID must be numeric',
            enabled=True
        )
    ]
    
    base_set = RuleSet('base', base_rules)
    dependent_set = RuleSet('dependent', dependent_rules, dependencies=['base'])
    
    validation_service.register_rule_set(base_set)
    validation_service.register_rule_set(dependent_set)
    
    # Test validation order
    result = validation_service.validate('test', {'id': ''})
    assert not result.is_valid
    assert len(result.errors) == 1  # Only base rule should fail
    assert 'required' in result.errors[0].lower()

def test_validation_severity_levels(validation_service):
    rules = [
        ValidationRule(
            rule_type=RuleType.REQUIRED,
            field_name='critical',
            parameters={},
            message='Critical field missing',
            severity=ValidationSeverity.ERROR
        ),
        ValidationRule(
            rule_type=RuleType.PATTERN,
            field_name='optional',
            parameters={'pattern': r'^\d+$'},
            message='Optional field should be numeric',
            severity=ValidationSeverity.WARNING
        )
    ]
    
    validation_service.register_rules('mixed_severity', rules)
    
    result = validation_service.validate('test', {
        'critical': '',
        'optional': 'abc'
    })
    
    assert not result.is_valid
    assert any(err.severity == ValidationSeverity.ERROR for err in result.errors)
    assert any(err.severity == ValidationSeverity.WARNING for err in result.errors)

def test_disabled_rule_handling(validation_service):
    rules = [
        ValidationRule(
            rule_type=RuleType.REQUIRED,
            field_name='test',
            parameters={},
            message='Test field required',
            enabled=False  # Disabled rule
        )
    ]
    
    validation_service.register_rules('disabled_rules', rules)
    
    result = validation_service.validate('test', {})
    assert result.is_valid  # Should pass since rule is disabled
    assert len(result.errors) == 0

def test_rule_set_error_collection(validation_service, sample_rule_set):
    validation_service.register_rule_set(sample_rule_set)
    
    # Test data with multiple validation errors
    invalid_data = {
        'name': '',           # Required rule violation
        'email': 'invalid'    # Pattern rule violation
    }
    
    result = validation_service.validate('test', invalid_data)
    
    # Verify all errors were collected
    assert len(result.errors) == 2
    assert any('name' in err.message.lower() for err in result.errors)
    assert any('email' in err.message.lower() for err in result.errors)

def test_validation_result_creation():
    errors = [
        ValidationRule(
            rule_type=RuleType.REQUIRED,
            field_name='test',
            parameters={},
            message='Test error',
            severity=ValidationSeverity.ERROR
        )
    ]
    
    result = ValidationResult(is_valid=False, errors=errors)
    assert not result.is_valid
    assert len(result.errors) == 1
    assert result.errors[0].message == 'Test error'