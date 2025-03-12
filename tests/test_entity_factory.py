import pytest
from datetime import datetime
from decimal import Decimal
from usaspending.entity_factory import EntityFactory
from usaspending.core.types import EntityType, ComponentConfig, TransformationRule
from usaspending.core.exceptions import EntityError

@pytest.fixture
def factory():
    return EntityFactory()

@pytest.fixture
def configured_factory(factory):
    config = ComponentConfig(
        name='test_factory',
        settings={
            'strict_mode': True,
            'entities': {
                'test_entity': {
                    'fields': {
                        'field1': {'type': 'string'},
                        'field2': {'type': 'decimal'},
                        'field3': {'type': 'string'}
                    },
                    'validations': {
                        'field1_required': {'field': 'field1', 'type': 'required'}
                    },
                    'transformations': {
                        'field2': [
                            TransformationRule(transform_type='decimal', parameters={})
                        ],
                        'field3': [
                            TransformationRule(transform_type='uppercase', parameters={})
                        ]
                    },
                    'metadata': {
                        'key_fields': ['field1'],
                        'version': '1.0'
                    }
                }
            }
        }
    )
    factory.configure(config)
    return factory

def test_factory_initialization(factory):
    assert factory._initialized is False
    assert len(factory._entities) == 0
    assert factory._strict_mode is False

def test_factory_configuration(configured_factory):
    assert configured_factory._initialized is True
    assert configured_factory._strict_mode is True
    assert 'test_entity' in configured_factory._entities
    assert len(configured_factory._entities['test_entity']['fields']) == 3

def test_register_entity(factory):
    entity_config = {
        'fields': {'name': {'type': 'string'}},
        'validations': {},
        'transformations': {},
        'metadata': {'version': '1.0'}
    }
    
    factory.register_entity(EntityType('new_entity'), entity_config)
    assert 'new_entity' in factory._entities
    assert factory._entities['new_entity']['fields'] == {'name': {'type': 'string'}}

def test_create_entity_success(configured_factory):
    data = {
        'field1': 'test',
        'field2': '123.45',
        'field3': 'hello'
    }
    
    result = configured_factory.create_entity(EntityType('test_entity'), data)
    
    assert result is not None
    assert result['type'] == 'test_entity'
    assert result['data']['field1'] == 'test'
    assert result['data']['field2'] == Decimal('123.45')
    assert result['data']['field3'] == 'HELLO'
    assert 'created' in result['metadata']
    assert result['metadata']['version'] == '1.0'

def test_create_entity_invalid_type(configured_factory):
    with pytest.raises(EntityError):
        configured_factory.create_entity(EntityType('invalid_entity'), {})

def test_create_entity_transformation_error(configured_factory):
    data = {
        'field1': 'test',
        'field2': 'not_a_number',  # This should fail decimal transformation
        'field3': 'hello'
    }
    
    if configured_factory._strict_mode:
        with pytest.raises(Exception):
            configured_factory.create_entity(EntityType('test_entity'), data)
    else:
        result = configured_factory.create_entity(EntityType('test_entity'), data)
        assert result is None

def test_get_entity_types(configured_factory):
    types = configured_factory.get_entity_types()
    assert len(types) == 1
    assert str(types[0]) == 'test_entity'

def test_get_entity_config(configured_factory):
    config = configured_factory.get_entity_config(EntityType('test_entity'))
    assert config is not None
    assert config.name == 'test_entity'
    assert len(config.fields) == 3
    assert config.key_fields == ['field1']

def test_cleanup(configured_factory):
    configured_factory.cleanup()
    assert configured_factory._initialized is False
    assert len(configured_factory._entities) == 0