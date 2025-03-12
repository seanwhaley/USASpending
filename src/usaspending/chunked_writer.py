"""Chunked writing system for efficient batch processing of entities."""
from typing import Dict, Any, List, Optional, Iterator, Generic, TypeVar, cast, Union
from abc import ABC, abstractmethod
import threading
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor
import time

from .core.interfaces import IEntityStore
from .core.logging_config import get_logger
from .core.entity_serializer import IEntitySerializer, EntitySerializer
from .core.types import EntityData, EntityType, DataclassProtocol

logger = get_logger(__name__)

T = TypeVar('T', bound=DataclassProtocol)

class IChunkedWriter(ABC, Generic[T]):
    """Interface for chunked writing operations."""
    
    @abstractmethod
    def write_chunk(self, entities: List[T]) -> bool:
        """Write a chunk of entities."""
        pass
    
    @abstractmethod
    def flush(self) -> None:
        """Flush any buffered entities."""
        pass
    
    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Get writing statistics."""
        pass

class ChunkedWriter(IChunkedWriter[T]):
    """Processes and writes entities in chunks."""
    
    def __init__(self, store: IEntityStore, serializer: IEntitySerializer[T],
                 chunk_size: int = 1000, max_retries: int = 3,
                 worker_threads: int = 4):
        """Initialize writer with store and configuration."""
        self.store = store
        self.serializer = serializer
        self.chunk_size = chunk_size
        self.max_retries = max_retries
        self.worker_threads = worker_threads
        
        self.buffer: List[T] = []
        self.stats: Dict[str, int] = {
            'total_entities': 0,
            'successful_writes': 0,
            'failed_writes': 0,
            'retries': 0,
            'chunks_processed': 0
        }
        self._lock = threading.Lock()
        self._queue: Queue[List[T]] = Queue()
        self._executor = ThreadPoolExecutor(max_workers=worker_threads)
        self._processing = False

    def _write_chunk_with_retry(self, chunk: List[T]) -> None:
        """Write chunk with retry logic."""
        retry_count = 0
        failed_entities = []
        successful_count = 0
        
        while retry_count < self.max_retries and chunk:
            remaining_entities = []
            
            try:
                # Process each entity in chunk
                for entity in chunk:
                    try:
                        # Serialize if needed
                        data = self.serializer.to_dict(entity) if hasattr(entity, '__dict__') else cast(Dict[str, Any], entity)
                        
                        # Save to store using proper EntityType
                        self.store.save_entity(
                            cast(EntityType, self.serializer.entity_type),
                            cast(EntityData, data)
                        )
                        successful_count += 1
                    except Exception as e:
                        # Track failed entity for retry
                        remaining_entities.append(entity)
                        logger.error(f"Entity write failed: {str(e)}")
                
                # Update chunk to only include failed entities
                chunk = remaining_entities

            except Exception as e:
                retry_count += 1
                chunk = chunk  # Keep all entities for retry
                
                with self._lock:
                    self.stats['retries'] += 1
                    
                if retry_count >= self.max_retries:
                    logger.error(
                        f"Failed to write chunk after {retry_count} retries: {e}"
                    )
                    failed_entities = chunk
                else:
                    backoff = min(5, retry_count)  # Cap maximum backoff
                    time.sleep(backoff)

        # Update stats once at the end
        with self._lock:
            self.stats['successful_writes'] += successful_count
            self.stats['failed_writes'] += len(failed_entities)
            self.stats['chunks_processed'] += 1

    def _process_buffer(self) -> bool:
        """Process current buffer."""
        if not self.buffer:
            return True
            
        # Prepare chunk for processing
        chunk = self.buffer[:self.chunk_size]
        self.buffer = self.buffer[self.chunk_size:]

        # Add to processing queue
        self._queue.put(chunk)
        
        # Start processing if not already running
        if not self._processing:
            self._start_processing()
            
        return True
        
    def _start_processing(self) -> None:
        """Start background processing of chunks."""
        self._processing = True
        self._executor.submit(self._process_queue)
        
    def _process_queue(self) -> None:
        """Process chunks from queue."""
        while True:
            try:
                # Get next chunk with timeout
                chunk = self._queue.get(timeout=1.0)
            except Empty:
                # Stop if queue is empty
                self._processing = False
                break
                
            try:
                self._write_chunk_with_retry(chunk)
            finally:
                self._queue.task_done()
                
    def write_chunk(self, entities: List[T]) -> bool:
        """Write a chunk of entities."""
        if not entities:
            return True
            
        with self._lock:
            self.stats['total_entities'] += len(entities)

        # Add to buffer
        self.buffer.extend(entities)
        
        # Process buffer if it reaches chunk size
        if len(self.buffer) >= self.chunk_size:
            return self._process_buffer()
            
        return True
        
    def flush(self) -> None:
        """Flush any remaining entities in buffer."""
        if self.buffer:
            self._process_buffer()
            
        # Wait for all processing to complete
        self._wait_for_processing()
        
    def get_stats(self) -> Dict[str, Any]:
        """Get writing statistics."""
        with self._lock:
            stats = dict(self.stats)
            
        # Calculate success rate avoiding float conversion
        total = stats['successful_writes'] + stats['failed_writes']
        if total > 0:
            success_rate = (stats['successful_writes'] * 100) // total
            stats['success_rate'] = success_rate
            
        return stats
        
    def _wait_for_processing(self) -> None:
        """Wait for all processing to complete."""
        self._queue.join()
        self._executor.shutdown(wait=True)

class AsyncChunkedWriter(IChunkedWriter[T]):
    """Asynchronous chunked writer implementation."""
    
    def __init__(self, writer: ChunkedWriter[T]):
        """Initialize with base writer."""
        self.writer = writer
        self._write_thread: Optional[threading.Thread] = None
        self._queue: Queue[List[T]] = Queue()
        self._stop_event = threading.Event()
        
    def write_chunk(self, entities: List[T]) -> bool:
        """Asynchronously write chunk of entities."""
        if not entities:
            return True
            
        # Start writer thread if not running
        if not self._write_thread or not self._write_thread.is_alive():
            self._start_writer_thread()
            
        # Add to queue
        self._queue.put(entities)
        return True
        
    def flush(self) -> None:
        """Flush pending writes and stop processing."""
        # Signal stop
        self._stop_event.set()
        
        # Wait for processing to complete
        if self._write_thread and self._write_thread.is_alive():
            self._write_thread.join()
            
        # Flush base writer
        self.writer.flush()
        
    def get_stats(self) -> Dict[str, Any]:
        """Get writing statistics."""
        stats = self.writer.get_stats()
        stats['queue_size'] = self._queue.qsize()
        return stats
        
    def _start_writer_thread(self) -> None:
        """Start background writer thread."""
        self._stop_event.clear()
        self._write_thread = threading.Thread(
            target=self._process_queue,
            daemon=True
        )
        self._write_thread.start()
        
    def _process_queue(self) -> None:
        """Process chunks from queue."""
        while not self._stop_event.is_set():
            try:
                # Get chunk with timeout
                chunk = self._queue.get(timeout=0.1)
                try:
                    self.writer.write_chunk(chunk)
                finally:
                    self._queue.task_done()
            except Empty:
                continue

__all__ = ['ChunkedWriter', 'AsyncChunkedWriter']