import pytest
from typing import Dict, Any, Optional
from src.usaspending.core.entity_base import (
    BaseEntityFactory,
    BaseEntityStore,
    BaseEntityMapper,
    BaseEntityMediator,
    EntityData
)
from src.usaspending.core.types import EntityType
from src.usaspending.core.exceptions import EntityError

class TestEntityFactory(BaseEntityFactory):
    def create_entity(self, entity_type: EntityType, data: Dict[str, Any]) -> Optional[EntityData]:
        return {'id': '1', 'type': str(entity_type), **data}

class TestEntityStore(BaseEntityStore):
    def __init__(self):
        self.entities: Dict[str, Dict[str, Any]] = {}
    
    def save_entity(self, entity_type: EntityType, entity: Dict[str, Any]) -> str:
        entity_id = entity.get('id', str(len(self.entities)))
        self.entities[entity_id] = entity
        return entity_id
    
    def get_entity(self, entity_type: EntityType, entity_id: str) -> Optional[Dict[str, Any]]:
        return self.entities.get(entity_id)

class TestEntityMapper(BaseEntityMapper):
    def map_entity(self, entity_type: EntityType, data: Dict[str, Any]) -> Dict[str, Any]:
        return {f"mapped_{k}": v for k, v in data.items()}

class TestEntityMediator(BaseEntityMediator):
    def __init__(self):
        super().__init__()
        self.factory = TestEntityFactory()
        self.store = TestEntityStore()
        self.mapper = TestEntityMapper()

@pytest.fixture
def factory():
    return TestEntityFactory()

@pytest.fixture
def store():
    return TestEntityStore()

@pytest.fixture
def mapper():
    return TestEntityMapper()

@pytest.fixture
def mediator():
    return TestEntityMediator()

def test_entity_factory_create():
    factory = TestEntityFactory()
    data = {'name': 'test', 'value': 123}
    entity = factory.create_entity(EntityType('test'), data)
    
    assert entity is not None
    assert entity['id'] == '1'
    assert entity['type'] == 'test'
    assert entity['name'] == 'test'
    assert entity['value'] == 123

def test_entity_store_operations():
    store = TestEntityStore()
    
    # Test save
    entity = {'id': 'test1', 'data': 'value1'}
    entity_id = store.save_entity(EntityType('test'), entity)
    assert entity_id == 'test1'
    
    # Test get
    retrieved = store.get_entity(EntityType('test'), 'test1')
    assert retrieved == entity
    
    # Test get nonexistent
    assert store.get_entity(EntityType('test'), 'nonexistent') is None

def test_entity_mapper_operations():
    mapper = TestEntityMapper()
    data = {'field1': 'value1', 'field2': 'value2'}
    
    mapped = mapper.map_entity(EntityType('test'), data)
    assert mapped == {'mapped_field1': 'value1', 'mapped_field2': 'value2'}

def test_entity_mediator_process_entity():
    mediator = TestEntityMediator()
    
    # Test successful processing
    result = mediator.process_entity(EntityType('test'), {'field': 'value'})
    assert result is not None
    
    # Verify entity was mapped, created and stored
    stored_entity = mediator.store.get_entity(EntityType('test'), result)
    assert stored_entity is not None
    assert 'mapped_field' in stored_entity

def test_entity_type_operations():
    entity_type = EntityType('test_entity')
    
    # Test string conversion
    assert str(entity_type) == 'test_entity'
    
    # Test equality
    assert entity_type == EntityType('test_entity')
    assert entity_type != EntityType('other_entity')
    
    # Test hash
    entities = {entity_type: 'value'}
    assert EntityType('test_entity') in entities

def test_entity_data_validation():
    # Test valid entity data
    valid_data = {'id': '1', 'type': 'test', 'data': 'value'}
    assert isinstance(valid_data, EntityData)
    
    # Test invalid entity data (missing required fields would raise type error)
    invalid_data = {'data': 'value'}
    with pytest.raises(TypeError):
        isinstance(invalid_data, EntityData)

def test_base_entity_factory_validation():
    factory = TestEntityFactory()
    
    # Test with None values
    with pytest.raises(EntityError):
        factory.create_entity(None, {'data': 'value'})
    
    with pytest.raises(EntityError):
        factory.create_entity(EntityType('test'), None)

def test_base_entity_store_validation():
    store = TestEntityStore()
    
    # Test with None values
    with pytest.raises(EntityError):
        store.save_entity(None, {'data': 'value'})
    
    with pytest.raises(EntityError):
        store.save_entity(EntityType('test'), None)
    
    with pytest.raises(EntityError):
        store.get_entity(None, 'test_id')

def test_base_entity_mapper_validation():
    mapper = TestEntityMapper()
    
    # Test with None values
    with pytest.raises(EntityError):
        mapper.map_entity(None, {'data': 'value'})
    
    with pytest.raises(EntityError):
        mapper.map_entity(EntityType('test'), None)

def test_entity_mediator_error_handling():
    mediator = TestEntityMediator()
    
    # Test with invalid data
    result = mediator.process_entity(EntityType('test'), None)
    assert result is None
    
    # Test with None entity type
    result = mediator.process_entity(None, {'data': 'value'})
    assert result is None

def test_entity_type_normalization():
    # Test various input formats
    assert str(EntityType('TEST_ENTITY')) == 'test_entity'
    assert str(EntityType('Test Entity')) == 'test_entity'
    assert str(EntityType('test-entity')) == 'test_entity'
    
    # Test equality after normalization
    assert EntityType('TEST_ENTITY') == EntityType('test_entity')
    assert EntityType('Test Entity') == EntityType('test_entity')
    assert EntityType('test-entity') == EntityType('test_entity')
