"""Entity caching module."""
from typing import Dict, Any, Optional, List, TypeVar, Generic
import time
from pathlib import Path

from .interfaces import IEntityCache, IEntitySerializer
from .text_file_cache import TextFileCache
from .exceptions import CacheError
from .logging_config import get_logger

logger = get_logger(__name__)

T = TypeVar('T')

class EntityCache(IEntityCache[T]):
    """Cache for entity instances with serialization support."""
    
    def __init__(self, serializer: IEntitySerializer[T], 
                 max_size: int = 1000, ttl_seconds: int = 300):
        """Initialize entity cache.
        
        Args:
            serializer: Entity serializer for cache storage
            max_size: Maximum number of cached entries
            ttl_seconds: Time to live in seconds for cache entries
        """
        self.serializer = serializer
        self.text_cache = TextFileCache(max_size, ttl_seconds)
        self.entity_cache: Dict[str, Dict[str, Any]] = {}
        self.stats = {
            'entity_hits': 0,
            'entity_misses': 0,
            'deserialization_errors': 0,
            'memory_cache_size': 0
        }

    def get(self, key: str) -> Optional[T]:
        """Get cached entity.
        
        Args:
            key: Cache key
            
        Returns:
            Cached entity or None if not found
        """
        try:
            # Check memory cache first
            if key in self.entity_cache:
                self.stats['entity_hits'] += 1
                return self.entity_cache[key]

            # Try text cache
            text_data = self.text_cache.get(key)
            if text_data:
                try:
                    entity = self.serializer.from_json(text_data)
                    self._cache_entity(key, entity)
                    self.stats['entity_hits'] += 1
                    return entity
                except Exception as e:
                    logger.error(f"Failed to deserialize entity for key {key}: {str(e)}")
                    self.stats['deserialization_errors'] += 1
                    return None

            self.stats['entity_misses'] += 1
            return None

        except Exception as e:
            logger.error(f"Error retrieving entity for key {key}: {str(e)}")
            return None

    def put(self, key: str, entity: T) -> None:
        """Cache entity instance.
        
        Args:
            key: Cache key
            entity: Entity to cache
        """
        try:
            # Serialize entity
            text_data = self.serializer.to_json(entity)
            
            # Store in text cache first
            self.text_cache.put(key, text_data)
            
            # Then cache in memory
            self._cache_entity(key, entity)

        except Exception as e:
            logger.error(f"Failed to cache entity for key {key}: {str(e)}")
            raise CacheError(f"Failed to cache entity: {str(e)}")

    def remove(self, key: str) -> None:
        """Remove entity from cache.
        
        Args:
            key: Cache key to remove
        """
        try:
            # Remove from both caches
            if key in self.entity_cache:
                del self.entity_cache[key]
                self.stats['memory_cache_size'] = len(self.entity_cache)
                
            self.text_cache.remove(key)

        except Exception as e:
            logger.error(f"Error removing cached entity for key {key}: {str(e)}")
            raise CacheError(f"Failed to remove cached entity: {str(e)}")

    def clear(self) -> None:
        """Clear all cached entities."""
        try:
            self.entity_cache.clear()
            self.text_cache.clear()
            self.stats['memory_cache_size'] = 0
            self.stats['entity_hits'] = 0
            self.stats['entity_misses'] = 0
            self.stats['deserialization_errors'] = 0

        except Exception as e:
            logger.error(f"Error clearing entity cache: {str(e)}")
            raise CacheError(f"Failed to clear entity cache: {str(e)}")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dictionary of cache statistics
        """
        stats = self.stats.copy()
        stats['text_cache'] = self.text_cache.get_stats()
        stats['memory_cache_size'] = len(self.entity_cache)
        return stats

    def _cache_entity(self, key: str, entity: T) -> None:
        """Cache entity in memory.
        
        Args:
            key: Cache key
            entity: Entity to cache
        """
        self.entity_cache[key] = entity
        self.stats['memory_cache_size'] = len(self.entity_cache)