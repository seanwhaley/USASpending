import pytest
from decimal import Decimal
from usaspending.entity_mapper import EntityMapper
from usaspending.core.types import ValidationRule, EntityType, ComponentConfig
from usaspending.core.exceptions import MappingError
from usaspending.core.adapters import StringAdapter, NumericAdapter, DateAdapter

@pytest.fixture
def mapper():
    return EntityMapper()

@pytest.fixture
def configured_mapper(mapper):
    config = ComponentConfig(
        name='test_mapper',
        settings={
            'mappings': {
                'test_entity': {
                    'required_fields': ['field1', 'field2'],
                    'field_mappings': {
                        'target_field1': {
                            'field': 'field1',
                            'adapter': StringAdapter()
                        },
                        'target_field2': {
                            'field': 'field2',
                            'adapter': NumericAdapter(decimal=True)
                        }
                    },
                    'derived_mappings': {
                        'sum_field': {
                            'type': 'sum',
                            'source_fields': ['field1', 'field2']
                        },
                        'concat_field': {
                            'type': 'concat',
                            'source_fields': ['field1', 'field2'],
                            'parameters': {'separator': '-'}
                        }
                    }
                }
            }
        }
    )
    mapper.configure(config)
    return mapper

def test_mapper_initialization(mapper):
    assert mapper._initialized is False
    assert len(mapper._mappings) == 0
    assert len(mapper._errors) == 0
    assert len(mapper._calculation_functions) > 0

def test_mapper_configuration(configured_mapper):
    assert configured_mapper._initialized is True
    assert 'test_entity' in configured_mapper._mappings
    assert len(configured_mapper._mappings['test_entity']['required_fields']) == 2

def test_validate_required_fields(configured_mapper):
    valid_data = {'field1': 'value1', 'field2': '100'}
    invalid_data = {'field1': 'value1'}
    
    assert configured_mapper.validate('test_entity', valid_data)
    assert not configured_mapper.validate('test_entity', invalid_data)
    assert any('Required field missing: field2' in err for err in configured_mapper.get_errors())

def test_direct_field_mapping(configured_mapper):
    source_data = {'field1': 'value1', 'field2': '100'}
    result = configured_mapper.map_entity(EntityType('test_entity'), source_data)
    
    assert result['target_field1'] == 'value1'
    assert result['target_field2'] == Decimal('100')

def test_derived_field_sum_calculation(configured_mapper):
    source_data = {'field1': '100', 'field2': '200'}
    result = configured_mapper.map_entity(EntityType('test_entity'), source_data)
    
    assert 'sum_field' in result
    assert result['sum_field'] == Decimal('300')

def test_derived_field_concat_calculation(configured_mapper):
    source_data = {'field1': 'Hello', 'field2': 'World'}
    result = configured_mapper.map_entity(EntityType('test_entity'), source_data)
    
    assert 'concat_field' in result
    assert result['concat_field'] == 'Hello-World'

def test_custom_calculation_function(configured_mapper):
    def multiply(values, **_):
        return Decimal(str(values[0])) * Decimal(str(values[1]))
    
    configured_mapper.register_calculation_function('multiply', multiply)
    
    # Add new derived mapping
    configured_mapper._mappings['test_entity']['derived_mappings']['product'] = {
        'type': 'multiply',
        'source_fields': ['field1', 'field2']
    }
    
    source_data = {'field1': '10', 'field2': '20'}
    result = configured_mapper.map_entity(EntityType('test_entity'), source_data)
    
    assert result['product'] == Decimal('200')

def test_invalid_calculation_type(configured_mapper):
    # Add invalid calculation type
    configured_mapper._mappings['test_entity']['derived_mappings']['invalid'] = {
        'type': 'invalid_type',
        'source_fields': ['field1', 'field2']
    }
    
    source_data = {'field1': 'value1', 'field2': 'value2'}
    result = configured_mapper.map_entity(EntityType('test_entity'), source_data)
    
    assert 'invalid' not in result
    assert any('Unsupported calculation type' in err for err in configured_mapper.get_errors())

def test_handle_missing_source_fields(configured_mapper):
    source_data = {'field1': '100'}  # field2 is missing
    result = configured_mapper.map_entity(EntityType('test_entity'), source_data)
    
    assert not result  # Should return empty dict due to validation failure
    assert len(configured_mapper.get_errors()) > 0

def test_clear_errors(configured_mapper):
    # Generate some errors
    source_data = {'field1': '100'}  # Missing field2
    configured_mapper.map_entity(EntityType('test_entity'), source_data)
    assert len(configured_mapper.get_errors()) > 0
    
    # Clear errors
    configured_mapper.clear_errors()
    assert len(configured_mapper.get_errors()) == 0

def test_invalid_entity_type(configured_mapper):
    source_data = {'field1': 'value1', 'field2': 'value2'}
    result = configured_mapper.map_entity(EntityType('invalid_entity'), source_data)
    
    assert not result  # Should return empty dict
    assert any('Unknown entity type' in err for err in configured_mapper.get_errors())