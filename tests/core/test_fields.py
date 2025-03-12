import pytest
from typing import Dict, Any, List
from usaspending.core.fields import (
    FieldDefinition,
    FieldDefinitionLoader,
    FieldGroup
)
from usaspending.core.types import (
    FieldType,
    ValidationRule,
    RuleType,
    ValidationSeverity,
    TransformationRule
)

@pytest.fixture
def sample_field_properties() -> Dict[str, Any]:
    return {
        'type': 'string',
        'required': True,
        'is_key': True,
        'groups': ['primary', 'required'],
        'validation_rules': [
            {
                'type': 'required',
                'message': 'Field is required',
                'severity': 'error'
            },
            {
                'type': 'pattern',
                'parameters': {'pattern': r'^[A-Z]+$'},
                'message': 'Must be uppercase letters',
                'severity': 'error'
            }
        ],
        'transformations': [
            {
                'type': 'uppercase',
                'parameters': {}
            }
        ]
    }

@pytest.fixture
def sample_field_definition(sample_field_properties) -> FieldDefinition:
    return FieldDefinitionLoader.create_field_definition('test_field', sample_field_properties)

def test_field_definition_creation(sample_field_properties):
    field_def = FieldDefinitionLoader.create_field_definition('test_field', sample_field_properties)
    
    assert field_def.name == 'test_field'
    assert field_def.type == FieldType.STRING
    assert field_def.required
    assert field_def.is_key
    assert len(field_def.groups) == 2
    assert 'primary' in field_def.groups
    assert 'required' in field_def.groups

def test_field_validation_rules(sample_field_definition):
    rules = sample_field_definition.validation_rules
    assert len(rules) == 2
    
    required_rule = rules[0]
    assert required_rule.rule_type == RuleType.REQUIRED
    assert required_rule.message == 'Field is required'
    assert required_rule.severity == ValidationSeverity.ERROR
    
    pattern_rule = rules[1]
    assert pattern_rule.rule_type == RuleType.PATTERN
    assert pattern_rule.parameters['pattern'] == r'^[A-Z]+$'
    assert pattern_rule.message == 'Must be uppercase letters'

def test_field_transformations(sample_field_definition):
    transformations = sample_field_definition.transformations
    assert len(transformations) == 1
    
    transform = transformations[0]
    assert transform.transform_type == 'uppercase'
    assert transform.parameters == {}

def test_field_definition_equality():
    props = {'type': 'string', 'required': True}
    field1 = FieldDefinitionLoader.create_field_definition('field1', props)
    field2 = FieldDefinitionLoader.create_field_definition('field1', props)
    field3 = FieldDefinitionLoader.create_field_definition('field3', props)
    
    assert field1 == field2
    assert field1 != field3

def test_field_type_conversion():
    # Test various type strings
    assert FieldDefinitionLoader._convert_type('string') == FieldType.STRING
    assert FieldDefinitionLoader._convert_type('integer') == FieldType.INTEGER
    assert FieldDefinitionLoader._convert_type('decimal') == FieldType.DECIMAL
    assert FieldDefinitionLoader._convert_type('boolean') == FieldType.BOOLEAN
    assert FieldDefinitionLoader._convert_type('date') == FieldType.DATE
    
    # Test invalid type
    with pytest.raises(ValueError):
        FieldDefinitionLoader._convert_type('invalid_type')

def test_field_group_creation():
    group = FieldGroup('test_group', ['field1', 'field2'])
    assert group.name == 'test_group'
    assert len(group.fields) == 2
    assert 'field1' in group.fields
    assert 'field2' in group.fields

def test_add_field_to_group():
    group = FieldGroup('test_group')
    group.add_field('field1')
    group.add_field('field2')
    
    assert len(group.fields) == 2
    assert 'field1' in group.fields
    assert 'field2' in group.fields

def test_remove_field_from_group():
    group = FieldGroup('test_group', ['field1', 'field2'])
    group.remove_field('field1')
    
    assert len(group.fields) == 1
    assert 'field1' not in group.fields
    assert 'field2' in group.fields

def test_field_group_contains():
    group = FieldGroup('test_group', ['field1', 'field2'])
    assert 'field1' in group
    assert 'field3' not in group

def test_field_group_iteration():
    fields = ['field1', 'field2', 'field3']
    group = FieldGroup('test_group', fields)
    
    iterated_fields = list(group)
    assert len(iterated_fields) == len(fields)
    for field in fields:
        assert field in iterated_fields

def test_create_field_definition_with_minimal_props():
    # Test with only required properties
    minimal_props = {
        'type': 'string'
    }
    field = FieldDefinitionLoader.create_field_definition('minimal_field', minimal_props)
    
    assert field.name == 'minimal_field'
    assert field.type == FieldType.STRING
    assert not field.required
    assert not field.is_key
    assert len(field.groups) == 0
    assert len(field.validation_rules) == 0
    assert len(field.transformations) == 0

def test_field_definition_properties():
    props = {
        'type': 'decimal',
        'required': True,
        'is_key': False,
        'description': 'A test decimal field',
        'default_value': '0.0',
        'format': '%.2f'
    }
    field = FieldDefinitionLoader.create_field_definition('decimal_field', props)
    
    assert field.type == FieldType.DECIMAL
    assert field.required
    assert not field.is_key
    assert field.description == 'A test decimal field'
    assert field.default_value == '0.0'
    assert field.format == '%.2f'

def test_field_validation_rule_creation():
    rule_config = {
        'type': 'range',
        'parameters': {'min': 0, 'max': 100},
        'message': 'Value must be between 0 and 100',
        'severity': 'warning'
    }
    
    rule = FieldDefinitionLoader._create_validation_rule(rule_config)
    assert rule.rule_type == RuleType.RANGE
    assert rule.parameters == {'min': 0, 'max': 100}
    assert rule.message == 'Value must be between 0 and 100'
    assert rule.severity == ValidationSeverity.WARNING

def test_field_transformation_rule_creation():
    transform_config = {
        'type': 'decimal',
        'parameters': {'precision': 2}
    }
    
    transform = FieldDefinitionLoader._create_transformation_rule(transform_config)
    assert transform.transform_type == 'decimal'
    assert transform.parameters == {'precision': 2}

def test_invalid_field_properties():
    # Test missing type
    with pytest.raises(ValueError):
        FieldDefinitionLoader.create_field_definition('test', {})
    
    # Test invalid validation rule
    invalid_props = {
        'type': 'string',
        'validation_rules': [{'type': 'invalid'}]
    }
    with pytest.raises(ValueError):
        FieldDefinitionLoader.create_field_definition('test', invalid_props)
    
    # Test invalid transformation
    invalid_props = {
        'type': 'string',
        'transformations': [{'type': ''}]
    }
    with pytest.raises(ValueError):
        FieldDefinitionLoader.create_field_definition('test', invalid_props)