import pytest
import os
import json
import sqlite3
from pathlib import Path
from typing import Dict, Any
from usaspending.core.storage import (
    IStorageStrategy,
    FileSystemStorage,
    SQLiteStorage,
    MemoryStorage
)
from usaspending.core.exceptions import StorageError

@pytest.fixture
def tmp_storage_dir(tmp_path):
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir()
    return storage_dir

@pytest.fixture
def fs_storage(tmp_storage_dir):
    return FileSystemStorage(str(tmp_storage_dir))

@pytest.fixture
def sqlite_storage(tmp_storage_dir):
    db_path = tmp_storage_dir / "test.db"
    return SQLiteStorage(str(db_path))

@pytest.fixture
def memory_storage():
    return MemoryStorage()

def test_filesystem_storage_save(fs_storage):
    # Test saving entity
    entity = {'id': 'test1', 'data': 'value1'}
    entity_id = fs_storage.save_entity('test_type', entity)
    
    # Verify file exists
    entity_path = Path(fs_storage._base_path) / 'test_type' / f"{entity_id}.json"
    assert entity_path.exists()
    
    # Verify content
    with open(entity_path) as f:
        stored_data = json.load(f)
    assert stored_data == entity

def test_filesystem_storage_get(fs_storage):
    # Save test entity
    entity = {'id': 'test1', 'name': 'Test Entity'}
    fs_storage.save_entity('test_type', entity)
    
    # Test retrieval
    retrieved = fs_storage.get_entity('test_type', 'test1')
    assert retrieved == entity
    
    # Test nonexistent entity
    assert fs_storage.get_entity('test_type', 'nonexistent') is None

def test_filesystem_storage_delete(fs_storage):
    # Save test entity
    entity = {'id': 'test1', 'data': 'value1'}
    fs_storage.save_entity('test_type', entity)
    
    # Test deletion
    assert fs_storage.delete_entity('test_type', 'test1')
    assert not fs_storage.get_entity('test_type', 'test1')
    
    # Test deleting nonexistent entity
    assert not fs_storage.delete_entity('test_type', 'nonexistent')

def test_sqlite_storage_initialization(tmp_storage_dir):
    db_path = tmp_storage_dir / "test.db"
    storage = SQLiteStorage(str(db_path))
    
    # Verify database and tables were created
    assert db_path.exists()
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Check if entities table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='entities'")
    assert cursor.fetchone() is not None
    
    conn.close()

def test_sqlite_storage_save(sqlite_storage):
    # Test saving entity
    entity = {'id': 'test1', 'data': 'value1'}
    entity_id = sqlite_storage.save_entity('test_type', entity)
    assert entity_id == 'test1'
    
    # Verify directly in database
    conn = sqlite3.connect(sqlite_storage._db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT entity_data FROM entities WHERE entity_type=? AND entity_id=?",
        ('test_type', 'test1')
    )
    row = cursor.fetchone()
    assert row is not None
    stored_data = json.loads(row[0])
    assert stored_data == entity
    conn.close()

def test_sqlite_storage_get(sqlite_storage):
    # Save test entity
    entity = {'id': 'test1', 'name': 'Test Entity'}
    sqlite_storage.save_entity('test_type', entity)
    
    # Test retrieval
    retrieved = sqlite_storage.get_entity('test_type', 'test1')
    assert retrieved == entity
    
    # Test nonexistent entity
    assert sqlite_storage.get_entity('test_type', 'nonexistent') is None

def test_sqlite_storage_delete(sqlite_storage):
    # Save test entity
    entity = {'id': 'test1', 'data': 'value1'}
    sqlite_storage.save_entity('test_type', entity)
    
    # Test deletion
    assert sqlite_storage.delete_entity('test_type', 'test1')
    assert not sqlite_storage.get_entity('test_type', 'test1')
    
    # Test deleting nonexistent entity
    assert not sqlite_storage.delete_entity('test_type', 'nonexistent')

def test_memory_storage_operations(memory_storage):
    # Test save
    entity1 = {'id': 'test1', 'data': 'value1'}
    entity_id = memory_storage.save_entity('test_type', entity1)
    assert entity_id == 'test1'
    
    # Test get
    retrieved = memory_storage.get_entity('test_type', 'test1')
    assert retrieved == entity1
    
    # Test delete
    assert memory_storage.delete_entity('test_type', 'test1')
    assert not memory_storage.get_entity('test_type', 'test1')

def test_storage_validation():
    storages = [
        FileSystemStorage('test_dir'),
        SQLiteStorage('test.db'),
        MemoryStorage()
    ]
    
    for storage in storages:
        # Test None values
        with pytest.raises(StorageError):
            storage.save_entity(None, {'id': 'test'})
        
        with pytest.raises(StorageError):
            storage.save_entity('test_type', None)
        
        with pytest.raises(StorageError):
            storage.get_entity(None, 'test')
        
        with pytest.raises(StorageError):
            storage.get_entity('test_type', None)

def test_filesystem_storage_path_creation(tmp_path):
    storage_dir = tmp_path / "nested" / "storage" / "path"
    storage = FileSystemStorage(str(storage_dir))
    
    # Test entity save creates directories
    entity = {'id': 'test1', 'data': 'value1'}
    storage.save_entity('test_type', entity)
    
    assert storage_dir.exists()
    assert (storage_dir / 'test_type').exists()

def test_sqlite_storage_concurrent_access(tmp_storage_dir):
    db_path = tmp_storage_dir / "test.db"
    storage1 = SQLiteStorage(str(db_path))
    storage2 = SQLiteStorage(str(db_path))
    
    # Test concurrent writes
    entity1 = {'id': 'test1', 'data': 'value1'}
    entity2 = {'id': 'test2', 'data': 'value2'}
    
    storage1.save_entity('test_type', entity1)
    storage2.save_entity('test_type', entity2)
    
    # Verify both entities were saved
    assert storage1.get_entity('test_type', 'test1') == entity1
    assert storage2.get_entity('test_type', 'test2') == entity2

def test_storage_entity_update():
    storages = [
        FileSystemStorage('test_dir'),
        SQLiteStorage('test.db'),
        MemoryStorage()
    ]
    
    for storage in storages:
        # Initial save
        entity = {'id': 'test1', 'data': 'initial'}
        storage.save_entity('test_type', entity)
        
        # Update
        updated_entity = {'id': 'test1', 'data': 'updated'}
        storage.save_entity('test_type', updated_entity)
        
        # Verify update
        retrieved = storage.get_entity('test_type', 'test1')
        assert retrieved['data'] == 'updated'

def test_storage_cleanup():
    # Test FileSystem cleanup
    fs_storage = FileSystemStorage('test_dir')
    fs_storage.cleanup()
    assert not os.path.exists('test_dir')
    
    # Test SQLite cleanup
    sqlite_storage = SQLiteStorage('test.db')
    sqlite_storage.cleanup()
    assert not os.path.exists('test.db')
    
    # Memory storage cleanup should not raise errors
    memory_storage = MemoryStorage()
    memory_storage.cleanup()