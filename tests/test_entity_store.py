import pytest
from unittest.mock import Mock, MagicMock
from usaspending.entity_store import EntityStore
from usaspending.core.types import EntityType, ComponentConfig
from usaspending.core.exceptions import StorageError
from usaspending.core.storage import SQLiteStorage, FileSystemStorage

@pytest.fixture
def store():
    return EntityStore()

@pytest.fixture
def configured_store_sqlite(store, tmp_path):
    config = ComponentConfig(
        name='test_store',
        settings={
            'strict_mode': True,
            'storage_type': 'sqlite',
            'path': str(tmp_path / 'test.db'),
            'max_connections': 3
        }
    )
    store.configure(config)
    return store

@pytest.fixture
def configured_store_fs(store, tmp_path):
    config = ComponentConfig(
        name='test_store',
        settings={
            'strict_mode': True,
            'storage_type': 'filesystem',
            'path': str(tmp_path / 'entities'),
            'max_files_per_dir': 100,
            'compression': True
        }
    )
    store.configure(config)
    return store

def test_store_initialization(store):
    assert store._initialized is False
    assert store._storage is None
    assert store._strict_mode is False

def test_store_configuration_sqlite(configured_store_sqlite):
    assert configured_store_sqlite._initialized is True
    assert configured_store_sqlite._strict_mode is True
    assert isinstance(configured_store_sqlite._storage, SQLiteStorage)

def test_store_configuration_filesystem(configured_store_fs):
    assert configured_store_fs._initialized is True
    assert configured_store_fs._strict_mode is True
    assert isinstance(configured_store_fs._storage, FileSystemStorage)

def test_save_entity(configured_store_fs):
    entity_type = EntityType('test_entity')
    entity_data = {'id': '1', 'name': 'Test'}
    
    entity_id = configured_store_fs.save_entity(entity_type, entity_data)
    assert entity_id is not None
    
    # Verify we can retrieve the saved entity
    retrieved = configured_store_fs.get_entity(entity_type, entity_id)
    assert retrieved == entity_data

def test_save_entity_uninitialized(store):
    with pytest.raises(StorageError, match="Entity store is not initialized"):
        store.save_entity(EntityType('test'), {})

def test_get_nonexistent_entity(configured_store_fs):
    result = configured_store_fs.get_entity(EntityType('test'), 'nonexistent')
    assert result is None

def test_delete_entity(configured_store_fs):
    entity_type = EntityType('test_entity')
    entity_data = {'id': '1', 'name': 'Test'}
    
    # Save and then delete
    entity_id = configured_store_fs.save_entity(entity_type, entity_data)
    assert configured_store_fs.delete_entity(entity_type, entity_id)
    
    # Verify it's gone
    assert configured_store_fs.get_entity(entity_type, entity_id) is None

def test_list_entities(configured_store_fs):
    entity_type = EntityType('test_entity')
    entities = [
        {'id': '1', 'name': 'Test 1'},
        {'id': '2', 'name': 'Test 2'}
    ]
    
    # Save entities
    for entity in entities:
        configured_store_fs.save_entity(entity_type, entity)
    
    # List and verify
    listed = list(configured_store_fs.list_entities(entity_type))
    assert len(listed) == 2
    assert all(e in entities for e in listed)

def test_count_entities(configured_store_fs):
    entity_type = EntityType('test_entity')
    entities = [
        {'id': '1', 'name': 'Test 1'},
        {'id': '2', 'name': 'Test 2'},
        {'id': '3', 'name': 'Test 3'}
    ]
    
    # Save entities
    for entity in entities:
        configured_store_fs.save_entity(entity_type, entity)
    
    assert configured_store_fs.count_entities(entity_type) == 3

def test_cleanup(configured_store_fs):
    # Save something first
    configured_store_fs.save_entity(EntityType('test'), {'id': '1'})
    
    # Cleanup should clear everything
    configured_store_fs.cleanup()
    
    # Try to save after cleanup - should raise error
    with pytest.raises(StorageError):
        configured_store_fs.save_entity(EntityType('test'), {'id': '2'})