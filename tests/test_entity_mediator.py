"""Tests for entity mediator functionality."""
import pytest
from typing import Dict, Any, Optional, List, Generator
from unittest.mock import Mock, patch

from usaspending.entity_mediator import EntityMediator
from usaspending.interfaces import (
    IEntityFactory, IEntityStore, IValidationMediator
)


class MockEntityFactory(IEntityFactory):
    """Mock entity factory for testing."""
    
    def __init__(self, should_create: bool = True) -> None:
        self._should_create = should_create
        self._created_entities: dict[str, Mock] = {}
        
    def create_entity(self, entity_type: str, data: Dict[str, Any]) -> Optional[Any]:
        if not self._should_create:
            return None
        entity = Mock()
        entity.entity_type = entity_type
        entity.data = data
        self._created_entities[entity_type] = entity
        return entity

    def get_entity_types(self) -> List[str]:
        return list(self._created_entities.keys())


class MockEntityStore(IEntityStore):
    """Mock entity store for testing."""
    
    def __init__(self, should_save: bool = True) -> None:
        self._should_save = should_save
        self._entities: dict[str, tuple[str, Mock]] = {}
        
    def save(self, entity_type: str, entity: Any) -> str:
        """Save entity and return its ID."""
        if not self._should_save:
            return ""
        # Get entity type from the entity object for validation
        if hasattr(entity, 'entity_type') and entity.entity_type != entity_type:
            return ""
            
        entity_id = f"{entity_type}-{len(self._entities) + 1}"
        self._entities[entity_id] = (entity_type, entity)
        return entity_id
        
    def get(self, entity_type: str, entity_id: str) -> Optional[Any]:
        stored = self._entities.get(entity_id)
        if stored and stored[0] == entity_type:
            return stored[1]
        return None
        
    def delete(self, entity_type: str, entity_id: str) -> bool:
        if entity_id in self._entities and self._entities[entity_id][0] == entity_type:
            del self._entities[entity_id]
            return True
        return False
    
    def list(self, entity_type: str) -> Generator[Any, None, None]:
        return (entity for _, (t, entity) in self._entities.items() if t == entity_type)
    
    def count(self, entity_type: str) -> int:
        return sum(1 for _, (t, _) in self._entities.items() if t == entity_type)


class MockValidationMediator(IValidationMediator):
    """Mock validation mediator for testing."""
    
    def __init__(self, should_validate: bool = True) -> None:
        self._should_validate = should_validate
        self._errors: list[str] = []
        self.validation_count = 0
        
    def validate_entity(self, entity_type: str, data: Dict[str, Any]) -> bool:
        self.validation_count += 1
        if not self._should_validate:
            self._errors.append(f"Entity validation failed for {entity_type}")
            return False
        return True
    
    def validate_field(self, field_name: str, value: Any, entity_type: Optional[str] = None) -> bool:
        self.validation_count += 1
        if not self._should_validate:
            self._errors.append(f"Field validation failed for {field_name}")
            return False
        return True
    
    def get_validation_errors(self) -> List[str]:
        return self._errors.copy()


@pytest.fixture
def mock_entity_factory() -> MockEntityFactory:
    """Create entity factory mock."""
    return MockEntityFactory()


@pytest.fixture
def mock_entity_store() -> MockEntityStore:
    """Create entity store mock."""
    return MockEntityStore()


@pytest.fixture
def mock_validation_mediator() -> MockValidationMediator:
    """Create validation mediator mock."""
    return MockValidationMediator()


@pytest.fixture
def entity_mediator(mock_entity_factory: MockEntityFactory, 
                   mock_entity_store: MockEntityStore,
                   mock_validation_mediator: MockValidationMediator) -> EntityMediator:
    """Create entity mediator with mocked dependencies."""
    return EntityMediator(mock_entity_factory, mock_entity_store, mock_validation_mediator)


def test_entity_mediator_initialization(entity_mediator: EntityMediator, 
                                     mock_entity_factory: MockEntityFactory,
                                     mock_entity_store: MockEntityStore, 
                                     mock_validation_mediator: MockValidationMediator) -> None:
    """Test mediator initialization."""
    assert entity_mediator._factory == mock_entity_factory
    assert entity_mediator._store == mock_entity_store
    assert entity_mediator._validator == mock_validation_mediator


def test_create_entity_success(entity_mediator: EntityMediator) -> None:
    """Test successful entity creation."""
    data = {"id": "test1", "name": "Test Entity"}
    entity = entity_mediator.create_entity("test_type", data)
    assert entity is not None
    assert entity.entity_type == "test_type"
    assert entity.data == data


def test_create_entity_validation_failure(entity_mediator: EntityMediator, 
                                        mock_validation_mediator: MockValidationMediator) -> None:
    """Test entity creation with validation failure."""
    mock_validation_mediator._should_validate = False
    data = {"id": "test1"}
    entity = entity_mediator.create_entity("test_type", data)
    assert entity is None
    assert len(mock_validation_mediator.get_validation_errors()) > 0


def test_create_entity_factory_failure(entity_mediator: EntityMediator, 
                                     mock_entity_factory: MockEntityFactory) -> None:
    """Test entity creation with factory failure."""
    mock_entity_factory._should_create = False
    data = {"id": "test1"}
    entity = entity_mediator.create_entity("test_type", data)
    assert entity is None


def test_store_entity_success(entity_mediator: EntityMediator) -> None:
    """Test successful entity storage."""
    data = {"id": "test1"}
    entity = entity_mediator.create_entity("test_type", data)
    assert entity is not None
    
    entity_id = entity_mediator.store_entity(entity)  # Remove entity_type argument
    assert entity_id != ""
    
    stored_entity = entity_mediator.get_entity("test_type", entity_id)
    assert stored_entity is not None
    assert stored_entity.data == data


def test_store_entity_failure(entity_mediator: EntityMediator, 
                            mock_entity_store: MockEntityStore) -> None:
    """Test entity storage failure."""
    mock_entity_store._should_save = False
    data = {"id": "test1"}
    entity = entity_mediator.create_entity("test_type", data)
    assert entity is not None
    
    entity_id = entity_mediator.store_entity(entity)  # Remove entity_type argument
    assert entity_id == ""


def test_validation_performance(entity_mediator: EntityMediator,
                              mock_validation_mediator: MockValidationMediator) -> None:
    """Test validation performance tracking."""
    initial_count = mock_validation_mediator.validation_count
    
    # Create and validate an entity
    data = {"id": "test1"}
    entity = entity_mediator.create_entity("test_type", data)
    assert entity is not None
    
    # Verify validation was performed
    assert mock_validation_mediator.validation_count > initial_count


def test_entity_type_validation(entity_mediator: EntityMediator) -> None:
    """Test entity type validation."""
    data = {"id": "test1"}
    
    # Valid entity type
    entity = entity_mediator.create_entity("test_type", data)
    assert entity is not None
    
    # Empty entity type should raise ValueError
    with pytest.raises(ValueError):
        entity_mediator.create_entity("", data)


def test_data_validation(entity_mediator: EntityMediator) -> None:
    """Test data validation."""
    # Empty data should raise ValueError
    with pytest.raises(ValueError):
        entity_mediator.create_entity("test_type", {})