"""Text file caching functionality."""
from typing import Dict, Any, Optional, List
import threading
import time
import os
from pathlib import Path

from .file_utils import read_text_file, write_text_file
from .exceptions import CacheError
from .logging_config import get_logger

logger = get_logger(__name__)

class TextFileCache:
    """Cache for text file contents with TTL expiration."""
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        """Initialize text file cache.
        
        Args:
            max_size: Maximum number of cache entries
            ttl_seconds: Time to live in seconds for cache entries
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'errors': 0
        }

    def get(self, key: str) -> Optional[str]:
        """Get cached text content.
        
        Args:
            key: Cache key
            
        Returns:
            Cached text content or None if not found
        """
        with self._lock:
            try:
                entry = self.cache.get(key)
                if not entry:
                    self.stats['misses'] += 1
                    return None

                # Check TTL
                if time.time() - entry['timestamp'] > self.ttl_seconds:
                    del self.cache[key]
                    self.stats['evictions'] += 1
                    return None

                self.stats['hits'] += 1
                return entry['content']

            except Exception as e:
                logger.error(f"Error retrieving from cache for key {key}: {str(e)}")
                self.stats['errors'] += 1
                return None

    def put(self, key: str, content: str) -> None:
        """Cache text content.
        
        Args:
            key: Cache key
            content: Text content to cache
        """
        with self._lock:
            try:
                # Evict if at max size
                if len(self.cache) >= self.max_size:
                    self._evict_oldest()

                # Add new entry
                self.cache[key] = {
                    'content': content,
                    'timestamp': time.time()
                }

            except Exception as e:
                logger.error(f"Failed to cache content for key {key}: {str(e)}")
                self.stats['errors'] += 1
                raise CacheError(f"Failed to cache content: {str(e)}")

    def remove(self, key: str) -> None:
        """Remove cached content.
        
        Args:
            key: Cache key to remove
        """
        with self._lock:
            try:
                if key in self.cache:
                    del self.cache[key]
            except Exception as e:
                logger.error(f"Error removing from cache for key {key}: {str(e)}")
                self.stats['errors'] += 1
                raise CacheError(f"Failed to remove from cache: {str(e)}")

    def clear(self) -> None:
        """Clear all cached content."""
        with self._lock:
            try:
                self.cache.clear()
                self.stats = {
                    'hits': 0,
                    'misses': 0,
                    'evictions': 0,
                    'errors': 0
                }
            except Exception as e:
                logger.error(f"Error clearing cache: {str(e)}")
                self.stats['errors'] += 1
                raise CacheError(f"Failed to clear cache: {str(e)}")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dictionary of cache statistics
        """
        with self._lock:
            stats = self.stats.copy()
            stats['size'] = len(self.cache)
            return stats

    def _evict_oldest(self) -> None:
        """Evict oldest cache entry."""
        if not self.cache:
            return

        oldest_key = min(
            self.cache.keys(),
            key=lambda k: self.cache[k]['timestamp']
        )
        del self.cache[oldest_key]
        self.stats['evictions'] += 1

    def load_file(self, file_path: str) -> Optional[str]:
        """Load file content into cache.
        
        Args:
            file_path: Path to file to load
            
        Returns:
            File content or None if error
        """
        try:
            content = read_text_file(file_path)
            if content is not None:
                self.put(file_path, content)
            return content
            
        except Exception as e:
            logger.error(f"Failed to load file {file_path}: {str(e)}")
            self.stats['errors'] += 1
            return None

    def save_file(self, file_path: str, content: str) -> bool:
        """Save content to file and cache.
        
        Args:
            file_path: Path to save file to
            content: Content to save
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if write_text_file(file_path, content):
                self.put(file_path, content)
                return True
            return False
            
        except Exception as e:
            logger.error(f"Failed to save file {file_path}: {str(e)}")
            self.stats['errors'] += 1
            return False