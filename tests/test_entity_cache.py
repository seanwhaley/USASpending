"""Tests for entity caching functionality."""
import pytest
from unittest.mock import Mock, patch
import time
import json
from typing import Dict, Any, Optional

from usaspending.entity_cache import EntityCache
from usaspending.text_file_cache import TextFileCache
from usaspending.interfaces import IEntitySerializer
from usaspending.exceptions import CacheError

class TestEntity:
    """Test entity class."""
    def __init__(self, id: str, data: Dict[str, Any]):
        self.id = id
        self.data = data

class TestEntitySerializer(IEntitySerializer[TestEntity]):
    """Test entity serializer."""
    def to_json(self, entity: TestEntity) -> str:
        return json.dumps({
            'id': entity.id,
            'data': entity.data
        })
        
    def from_json(self, json_str: str) -> TestEntity:
        data = json.loads(json_str)
        return TestEntity(data['id'], data['data'])
        
    def to_dict(self, entity: TestEntity) -> Dict[str, Any]:
        return {'id': entity.id, 'data': entity.data}
        
    def from_dict(self, data: Dict[str, Any]) -> TestEntity:
        return TestEntity(data['id'], data['data'])
        
    def to_csv_row(self, entity: TestEntity) -> str:
        return [entity.id, json.dumps(entity.data)]
        
    def from_csv_row(self, row: str, headers: str) -> TestEntity:
        return TestEntity(row[0], json.loads(row[1]))

@pytest.fixture
def serializer():
    """Create test serializer."""
    return TestEntitySerializer()

@pytest.fixture
def cache(serializer):
    """Create test cache."""
    return EntityCache(serializer, max_size=10, ttl_seconds=1)

def test_cache_put_and_get(cache):
    """Test basic caching operations."""
    entity = TestEntity('test1', {'value': 123})
    cache.put('key1', entity)
    
    result = cache.get('key1')
    assert result is not None
    assert result.id == 'test1'
    assert result.data == {'value': 123}

def test_cache_memory_hit(cache):
    """Test memory cache hit."""
    entity = TestEntity('test1', {'value': 123})
    cache.put('key1', entity)
    
    # First get should cache in memory
    cache.get('key1')
    initial_stats = cache.get_stats()
    
    # Second get should hit memory cache
    cache.get('key1')
    final_stats = cache.get_stats()
    
    assert final_stats['entity_hits'] == initial_stats['entity_hits'] + 1
    assert final_stats['entity_misses'] == initial_stats['entity_misses']

def test_cache_text_fallback(cache):
    """Test fallback to text cache."""
    entity = TestEntity('test1', {'value': 123})
    cache.put('key1', entity)
    
    # Clear memory cache
    cache.entity_cache.clear()
    
    # Should still get from text cache
    result = cache.get('key1')
    assert result is not None
    assert result.id == 'test1'

def test_cache_expiration(cache):
    """Test cache entry expiration."""
    entity = TestEntity('test1', {'value': 123})
    cache.put('key1', entity)
    
    # Wait for TTL
    time.sleep(1.1)
    
    result = cache.get('key1')
    assert result is None
    
    stats = cache.get_stats()
    assert stats['entity_misses'] > 0

def test_cache_remove(cache):
    """Test removing cache entries."""
    entity = TestEntity('test1', {'value': 123})
    cache.put('key1', entity)
    
    cache.remove('key1')
    
    assert cache.get('key1') is None
    assert 'key1' not in cache.entity_cache
    assert cache.text_cache.get('key1') is None

def test_cache_clear(cache):
    """Test clearing all cache entries."""
    entity1 = TestEntity('test1', {'value': 123})
    entity2 = TestEntity('test2', {'value': 456})
    cache.put('key1', entity1)
    cache.put('key2', entity2)
    
    cache.clear()
    
    assert cache.get('key1') is None
    assert cache.get('key2') is None
    assert len(cache.entity_cache) == 0
    assert len(cache.text_cache.cache) == 0

def test_cache_error_handling(cache):
    """Test error handling during caching."""
    entity = TestEntity('test1', {'value': 123})
    
    # Mock serializer to raise error
    cache.serializer.to_json = Mock(side_effect=Exception("Serialization failed"))
    
    with pytest.raises(CacheError):
        cache.put('key1', entity)
        
    stats = cache.get_stats()
    assert stats['deserialization_errors'] == 0  # Should not increment on put errors

def test_cache_stats(cache):
    """Test cache statistics."""
    entity = TestEntity('test1', {'value': 123})
    cache.put('key1', entity)
    
    # Generate some stats
    cache.get('key1')  # Hit
    cache.get('missing')  # Miss
    
    stats = cache.get_stats()
    assert 'entity_hits' in stats
    assert 'entity_misses' in stats
    assert 'text_cache' in stats
    assert 'memory_cache_size' in stats
    
    assert stats['entity_hits'] > 0
    assert stats['entity_misses'] > 0
    assert stats['memory_cache_size'] == 1