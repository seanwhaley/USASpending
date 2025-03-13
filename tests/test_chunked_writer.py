import pytest
from dataclasses import dataclass
from typing import Dict, Any, List
import time
from src.usaspending.chunked_writer import ChunkedWriter, AsyncChunkedWriter
from src.usaspending.core.types import EntityType, EntityData
from src.usaspending.core.interfaces import IEntityStore
from src.usaspending.core.entity_serializer import IEntitySerializer

@dataclass
class EntityForTest:
    id: str
    value: str

class MockEntityStore(IEntityStore):
    def __init__(self, fail_pattern: str = ""):
        self.entities: Dict[str, Dict[str, Any]] = {}
        self.fail_pattern = fail_pattern
    
    def save_entity(self, entity_type: EntityType, entity: EntityData) -> str:
        if self.fail_pattern and entity.get('id', '').startswith(self.fail_pattern):
            raise Exception(f"Simulated failure for {entity['id']}")
        self.entities[entity['id']] = entity
        return entity['id']
    
    def get_entity(self, entity_type: EntityType, entity_id: str) -> Dict[str, Any]:
        return self.entities.get(entity_id, {})

class MockSerializer(IEntitySerializer[EntityForTest]):
    def __init__(self):
        self.entity_type = EntityType('test')
    
    def to_dict(self, entity: EntityForTest) -> Dict[str, Any]:
        return {'id': entity.id, 'value': entity.value}
    
    def from_dict(self, data: Dict[str, Any]) -> EntityForTest:
        return EntityForTest(id=data['id'], value=data['value'])

@pytest.fixture
def store():
    return MockEntityStore()

@pytest.fixture
def failing_store():
    return MockEntityStore(fail_pattern='fail_')

@pytest.fixture
def serializer():
    return MockSerializer()

@pytest.fixture
def writer(store, serializer):
    return ChunkedWriter(
        store=store,
        serializer=serializer,
        chunk_size=2,
        max_retries=2,
        worker_threads=1
    )

@pytest.fixture
def async_writer(writer):
    return AsyncChunkedWriter(writer)

def test_chunked_writer_initialization(writer):
    assert writer.chunk_size == 2
    assert writer.max_retries == 2
    assert len(writer.buffer) == 0
    assert writer.stats['total_entities'] == 0

def test_write_chunk_success(writer):
    entities = [
        EntityForTest(id='1', value='test1'),
        EntityForTest(id='2', value='test2')
    ]
    
    assert writer.write_chunk(entities)
    writer.flush()
    
    stats = writer.get_stats()
    assert stats['successful_writes'] == 2
    assert stats['failed_writes'] == 0
    assert stats['chunks_processed'] == 1

def test_write_chunk_with_retries(failing_store, serializer):
    writer = ChunkedWriter(
        store=failing_store,
        serializer=serializer,
        chunk_size=2,
        max_retries=3,
        worker_threads=1
    )
    
    entities = [
        EntityForTest(id='fail_1', value='test1'),  # Will fail
        EntityForTest(id='2', value='test2')        # Will succeed
    ]
    
    assert writer.write_chunk(entities)
    writer.flush()
    
    stats = writer.get_stats()
    assert stats['successful_writes'] == 1
    assert stats['failed_writes'] == 1
    assert stats['retries'] > 0

def test_buffer_auto_flush(writer):
    # Add entities one by one
    for i in range(5):
        writer.write_chunk([EntityForTest(id=str(i), value=f'test{i}')])
    
    # Buffer should auto-flush when reaching chunk_size
    writer.flush()
    stats = writer.get_stats()
    assert stats['chunks_processed'] == 3  # 2+2+1 entities
    assert stats['successful_writes'] == 5

def test_async_writer_initialization(async_writer):
    assert async_writer.writer is not None
    assert async_writer._write_thread is None
    assert async_writer._queue.empty()

def test_async_write_chunk(async_writer):
    entities = [
        EntityForTest(id='async1', value='test1'),
        EntityForTest(id='async2', value='test2')
    ]
    
    assert async_writer.write_chunk(entities)
    # Small delay to allow processing
    time.sleep(0.1)
    async_writer.flush()
    
    stats = async_writer.get_stats()
    assert stats['successful_writes'] == 2
    assert stats['failed_writes'] == 0
    assert stats['queue_size'] == 0

def test_async_writer_multiple_chunks(async_writer):
    # Write multiple chunks rapidly
    for i in range(5):
        entities = [
            EntityForTest(id=f'batch{i}_1', value=f'test{i}_1'),
            EntityForTest(id=f'batch{i}_2', value=f'test{i}_2')
        ]
        async_writer.write_chunk(entities)
    
    # Flush and verify
    async_writer.flush()
    stats = async_writer.get_stats()
    assert stats['successful_writes'] == 10  # 5 batches * 2 entities
    assert stats['queue_size'] == 0

def test_async_writer_error_handling(failing_store, serializer):
    writer = ChunkedWriter(failing_store, serializer, chunk_size=2)
    async_writer = AsyncChunkedWriter(writer)
    
    # Mix of failing and successful entities
    entities = [
        EntityForTest(id='fail_async', value='test1'),
        EntityForTest(id='success_async', value='test2')
    ]
    
    assert async_writer.write_chunk(entities)
    time.sleep(0.1)  # Allow processing
    async_writer.flush()
    
    stats = async_writer.get_stats()
    assert stats['successful_writes'] == 1
    assert stats['failed_writes'] == 1

def test_stats_calculation(writer):
    # Write mix of successful and failing entities
    entities = [
        EntityForTest(id='stats1', value='test1'),
        EntityForTest(id='stats2', value='test2')
    ]
    
    writer.write_chunk(entities)
    writer.flush()
    
    stats = writer.get_stats()
    assert 'success_rate' in stats
    assert stats['success_rate'] == 100  # All successful
    assert stats['total_entities'] == 2
