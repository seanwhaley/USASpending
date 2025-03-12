"""Core caching functionality."""
from typing import Dict, Any, Optional, TypeVar, Generic, cast, Union, Protocol
from pathlib import Path
import json
import threading
from abc import ABC, abstractmethod
from .types import EntityKey, EntityData
from .exceptions import CacheError
from .utils import (
    safe_operation,
    atomic_operation,
    ensure_directory,
    read_json_file,
    write_json_file,
    LRUCache
)

# Define a type for JSON serializable data
class JsonSerializable(Protocol):
    """Protocol for JSON serializable objects."""
    def __json__(self) -> Dict[str, Any]: ...

T = TypeVar('T')
CacheData = Union[Dict[str, Any], list, str, int, float, bool, None]

class BaseCache(ABC, Generic[T]):
    """Base cache interface."""
    
    @abstractmethod
    def get(self, key: str) -> Optional[T]:
        """Get item from cache."""
        pass
        
    @abstractmethod
    def put(self, key: str, value: T) -> None:
        """Add item to cache."""
        pass
        
    @abstractmethod
    def remove(self, key: str) -> bool:
        """Remove item from cache."""
        pass
        
    @abstractmethod
    def clear(self) -> None:
        """Clear all items from cache."""
        pass

    @property
    @abstractmethod
    def size(self) -> int:
        """Return number of items in cache."""
        pass

class MemoryCache(BaseCache[T]):
    """Thread-safe memory cache implementation."""
    
    def __init__(self, capacity: int):
        self.cache = LRUCache(capacity)
        
    def get(self, key: str) -> Optional[T]:
        """Get item from memory cache."""
        return cast(Optional[T], self.cache.get(key))
        
    def put(self, key: str, value: T) -> None:
        """Add item to memory cache."""
        self.cache.put(key, value)
        
    def remove(self, key: str) -> bool:
        """Remove item from memory cache."""
        if self.cache.get(key) is not None:
            self.cache.remove(key)
            return True
        return False
        
    def clear(self) -> None:
        """Clear memory cache."""
        self.cache = LRUCache(self.cache.capacity)

    @property
    def size(self) -> int:
        """Return number of items in cache."""
        return len(self.cache)

class FileCache(BaseCache[T]):
    """File-based cache implementation."""
    
    def __init__(self, cache_dir: str, max_files: int = 1000):
        self.cache_dir = Path(cache_dir)
        self.max_files = max_files
        self._lock = threading.Lock()
        ensure_directory(str(self.cache_dir))
        
    def _get_cache_path(self, key: str) -> Path:
        """Get path for cached file."""
        # Use key hash to distribute files
        key_hash = hash(key) % self.max_files
        path = self.cache_dir / str(key_hash)
        ensure_directory(str(path))
        return path / f"{key}.json"
        
    @safe_operation
    def get(self, key: str) -> Optional[T]:
        """Get item from file cache."""
        path = self._get_cache_path(key)
        if path.exists():
            with self._lock:
                try:
                    data = read_json_file(str(path))
                    if not isinstance(data, dict):
                        raise CacheError(f"Invalid cache data format for key {key}")
                    value = data.get('value')
                    if value is None:
                        return None
                    # For JSON-serializable types, ensure the value matches expected type
                    if isinstance(value, (dict, list, str, int, float, bool)) or value is None:
                        return cast(T, value)
                    raise CacheError(f"Invalid cached value type for key {key}")
                except json.JSONDecodeError as e:
                    raise CacheError(f"Failed to decode cache data: {str(e)}")
        return None
        
    @safe_operation
    @atomic_operation
    def put(self, key: str, value: T) -> None:
        """Add item to file cache."""
        path = self._get_cache_path(key)
        with self._lock:
            try:
                # Convert to JSON-serializable format and wrap in a dict
                json_data: Dict[str, Any] = {'value': None}
                if hasattr(value, '__json__'):
                    json_data['value'] = cast(JsonSerializable, value).__json__()
                elif isinstance(value, (dict, list, str, int, float, bool)) or value is None:
                    json_data['value'] = value
                else:
                    raise CacheError(f"Value of type {type(value)} is not JSON serializable")
                    
                write_json_file(str(path), json_data)
            except (TypeError, json.JSONDecodeError) as e:
                raise CacheError(f"Failed to serialize cache value: {str(e)}")
            
    @safe_operation
    def remove(self, key: str) -> bool:
        """Remove item from file cache."""
        path = self._get_cache_path(key)
        with self._lock:
            if path.exists():
                path.unlink()
                return True
        return False
        
    @safe_operation
    def clear(self) -> None:
        """Clear file cache."""
        with self._lock:
            for path in self.cache_dir.rglob("*.json"):
                path.unlink()

    @property
    def size(self) -> int:
        """Return number of items in cache."""
        count = 0
        with self._lock:
            for _ in self.cache_dir.rglob("*.json"):
                count += 1
        return count

class TwoLevelCache(BaseCache[T]):
    """Two-level cache with memory and file backing."""
    
    def __init__(self, memory_cache: MemoryCache[T], file_cache: FileCache[T]):
        self.memory_cache = memory_cache
        self.file_cache = file_cache
        
    def get(self, key: str) -> Optional[T]:
        """Get item from cache, trying memory first."""
        # Try memory cache first
        value = self.memory_cache.get(key)
        if value is not None:
            return value
            
        # Try file cache
        value = self.file_cache.get(key)
        if value is not None:
            # Populate memory cache
            self.memory_cache.put(key, value)
            return value
            
        return None
        
    def put(self, key: str, value: T) -> None:
        """Add item to both caches."""
        self.memory_cache.put(key, value)
        self.file_cache.put(key, value)
        
    def remove(self, key: str) -> bool:
        """Remove item from both caches."""
        memory_removed = self.memory_cache.remove(key)
        file_removed = self.file_cache.remove(key)
        return memory_removed or file_removed
        
    def clear(self) -> None:
        """Clear both caches."""
        self.memory_cache.clear()
        self.file_cache.clear()

    @property
    def size(self) -> int:
        """Return number of items in cache."""
        return self.memory_cache.size

class EntityCache:
    """Entity-specific cache implementation."""
    
    def __init__(self, cache_dir: str, memory_capacity: int = 1000, max_files: int = 1000):
        self.memory_cache = MemoryCache[EntityData](memory_capacity)
        self.file_cache = FileCache[EntityData](cache_dir, max_files)
        self.cache = TwoLevelCache(self.memory_cache, self.file_cache)
        
    def get_entity(self, entity_type: str, key: EntityKey) -> Optional[EntityData]:
        """Get cached entity."""
        cache_key = f"{entity_type}:{key}"
        return self.cache.get(cache_key)
        
    def cache_entity(self, entity_type: str, key: EntityKey, data: EntityData) -> None:
        """Cache entity data."""
        cache_key = f"{entity_type}:{key}"
        self.cache.put(cache_key, data)
        
    def remove_entity(self, entity_type: str, key: EntityKey) -> bool:
        """Remove cached entity."""
        cache_key = f"{entity_type}:{key}"
        return self.cache.remove(cache_key)

    def clear_type(self, entity_type: str) -> None:
        """Clear cache for an entity type."""
        # Only clear entries matching the entity type
        keys_to_remove = []
        
        # Find all keys in memory cache for this type
        for key in self.memory_cache.cache.keys():
            if key.startswith(f"{entity_type}:"):
                keys_to_remove.append(key)
                
        # Remove from both caches
        for key in keys_to_remove:
            self.cache.remove(key)

        # Clear matching files from file cache
        with self.file_cache._lock:
            for path in self.file_cache.cache_dir.rglob("*.json"):
                if path.stem.startswith(f"{entity_type}:"):
                    path.unlink()

__all__ = [
    'BaseCache',
    'MemoryCache',
    'FileCache',
    'TwoLevelCache',
    'EntityCache'
]