import pytest
from unittest.mock import Mock, MagicMock
from src.usaspending.entity_mediator import USASpendingEntityMediator
from src.usaspending.core.types import ValidationRule, EntityType, ComponentConfig
from src.usaspending.core.exceptions import EntityError
from src.usaspending.core.adapters import StringAdapter, MoneyAdapter, DateAdapter

@pytest.fixture
def mock_factory():
    factory = Mock()
    test_entity = {
        'id': '1',
        'amount': '$1000.00',
        'date': '2024-01-01',
        'description': 'Test entity'
    }
    factory.create_entity.return_value = test_entity
    return factory

@pytest.fixture
def mock_store():
    store = Mock()
    store.save_entity.return_value = '1'
    store.get_entity.return_value = {
        'id': '1',
        'amount': '$1000.00',
        'date': '2024-01-01',
        'description': 'Test entity'
    }
    return store

@pytest.fixture
def mock_mapper():
    mapper = Mock()
    mapper.map_entity.return_value = {
        'id': '1',
        'amount': '$1000.00',
        'date': '2024-01-01',
        'description': 'Test entity',
        'mapped': True
    }
    return mapper

@pytest.fixture
def mediator(mock_factory, mock_store, mock_mapper):
    return USASpendingEntityMediator(mock_factory, mock_store, mock_mapper)

@pytest.fixture
def configured_mediator(mediator):
    config = ComponentConfig(
        name='test_mediator',
        settings={
            'strict_mode': True,
            'batch_size': 100,
            'entities': {
                'contract': {
                    'adapters': {
                        'amount': MoneyAdapter(),
                        'date': DateAdapter(),
                        'description': StringAdapter()
                    },
                    'validations': [
                        {
                            'field': 'amount',
                            'rule': 'required',
                            'message': 'Amount is required'
                        },
                        {
                            'field': 'date',
                            'rule': 'required',
                            'message': 'Date is required'
                        }
                    ]
                }
            }
        }
    )
    mediator.configure(config)
    return mediator

def test_mediator_initialization(mediator):
    assert mediator._factory is not None
    assert mediator._store is not None
    assert mediator._mapper is not None
    assert mediator._initialized is False
    assert mediator._strict_mode is False
    assert mediator._batch_size == 1000

def test_mediator_configuration(configured_mediator):
    assert configured_mediator._initialized is True
    assert configured_mediator._strict_mode is True
    assert configured_mediator._batch_size == 100
    assert 'contract' in configured_mediator._entity_configs

def test_add_validation_rule(mediator):
    rule = ValidationRule(
        rule_type='required',
        field_name='amount',
        parameters={},
        message='Amount is required',
        enabled=True
    )
    mediator.add_validation_rule(EntityType('contract'), rule)
    assert len(mediator.get_validation_rules(EntityType('contract'))) == 1

def test_process_entity_success(configured_mediator):
    entity_data = {
        'id': '1',
        'amount': '$1000.00',
        'date': '2024-01-01',
        'description': 'Test entity'
    }
    entity_id = configured_mediator.process_entity(EntityType('contract'), entity_data)
    assert entity_id == '1'
    assert configured_mediator.get_errors(EntityType('contract')) == []

def test_process_entity_validation_failure(configured_mediator):
    entity_data = {
        'id': '1',
        'description': 'Test entity'
        # Missing required amount and date
    }
    with pytest.raises(EntityError):
        configured_mediator.process_entity(EntityType('contract'), entity_data)
    assert len(configured_mediator.get_errors(EntityType('contract'))) > 0

def test_batch_processing(configured_mediator):
    entities = [
        {
            'id': str(i),
            'amount': f'${1000 * i}.00',
            'date': '2024-01-01',
            'description': f'Test entity {i}'
        }
        for i in range(1, 4)
    ]
    
    results = configured_mediator.process_batch(EntityType('contract'), entities)
    assert len(results) == 3
    assert all(id is not None for id in results)

def test_cleanup(configured_mediator):
    configured_mediator.cleanup()
    configured_mediator._store.cleanup.assert_called_once()

def test_invalid_configuration():
    mediator = USASpendingEntityMediator(Mock(), Mock(), Mock())
    invalid_config = ComponentConfig(
        name='test_mediator',
        settings={
            # Missing required settings
        }
    )
    with pytest.raises(EntityError):
        mediator.configure(invalid_config)

def test_validation_rule_processing(configured_mediator):
    # Test validation with custom rule
    rule = ValidationRule(
        rule_type='range',
        field_name='amount',
        parameters={'min': 0, 'max': 10000},
        message='Amount must be between {min} and {max}',
        enabled=True
    )
    configured_mediator.add_validation_rule(EntityType('contract'), rule)
    
    # Valid entity
    valid_entity = {
        'id': '1',
        'amount': '$5000.00',
        'date': '2024-01-01',
        'description': 'Test entity'
    }
    entity_id = configured_mediator.process_entity(EntityType('contract'), valid_entity)
    assert entity_id is not None
    
    # Invalid entity
    invalid_entity = {
        'id': '2',
        'amount': '$15000.00',  # Exceeds max
        'date': '2024-01-01',
        'description': 'Test entity'
    }
    with pytest.raises(EntityError):
        configured_mediator.process_entity(EntityType('contract'), invalid_entity)
    assert any('Amount must be between' in err for err in configured_mediator.get_errors(EntityType('contract')))
