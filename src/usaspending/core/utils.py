"""Core utility functions and decorators."""
from functools import wraps
import threading
from typing import TypeVar, Dict, Any, Callable, cast, Union, List, Iterator, Optional, Type
import logging
import yaml
import json
from pathlib import Path
import inspect
import time
from types import TracebackType

logger = logging.getLogger(__name__)

# Type variables for generic functions
T = TypeVar('T')
F = TypeVar('F', bound=Callable[..., Any])

class ThreadSafeMeta(type):
    """Metaclass for thread-safe singleton pattern."""
    _instances: Dict[Type, Any] = {}
    _locks: Dict[Type, threading.Lock] = {}

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        """Create or return singleton instance."""
        if cls not in cls._instances:
            if cls not in cls._locks:
                cls._locks[cls] = threading.Lock()
            with cls._locks[cls]:
                if cls not in cls._instances:
                    cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]

class ThreadSafeSingleton(metaclass=ThreadSafeMeta):
    """Base class for thread-safe singleton pattern."""
    pass

def read_yaml_file(file_path: Union[str, Path]) -> Dict[str, Any]:
    """Read YAML file and return contents."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.error(f"Error reading YAML file {file_path}: {str(e)}")
        return {}

def read_json_file(file_path: Union[str, Path]) -> Dict[str, Any]:
    """Read JSON file and return contents."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f) or {}
    except Exception as e:
        logger.error(f"Error reading JSON file {file_path}: {str(e)}")
        return {}

def write_json_file(file_path: Union[str, Path], data: Dict[str, Any]) -> bool:
    """Write data to JSON file."""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error writing JSON file {file_path}: {str(e)}")
        return False

def safe_operation(func: F) -> F:
    """Decorator for safe operation handling."""
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            instance = args[0] if args else None
            if instance and hasattr(instance, '_errors'):
                error_msg = f"{func.__name__} failed: {str(e)}"
                instance._errors.append(error_msg)
            if hasattr(instance, '_strict_mode') and getattr(instance, '_strict_mode', False):
                raise
            logger.error(f"Operation {func.__name__} failed: {str(e)}")
            return None
    return cast(F, wrapper)

def ensure_directory(path: Union[str, Path]) -> bool:
    """Ensure a directory exists."""
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Error creating directory {path}: {str(e)}")
        return False

def cleanup(instance: Any) -> None:
    """Clean up resources and perform shutdown.
    
    Args:
        instance: Object instance to clean up
    """
    # Identify cleanup methods based on naming convention
    cleanup_methods = [
        method for name, method in inspect.getmembers(instance, inspect.ismethod)
        if name.startswith('cleanup_') or name == 'cleanup'
    ]
    
    # Execute cleanup methods
    for method in cleanup_methods:
        try:
            method()
        except Exception as e:
            logger.error(f"Cleanup method {method.__name__} failed: {str(e)}")

class Timer:
    """Simple context manager for timing operations."""
    
    def __init__(self) -> None:
        self.elapsed: float = 0.0
        self._start: Optional[float] = None

    def __enter__(self) -> 'Timer':
        self._start = time.time()
        return self

    def __exit__(self, _exc_type: Optional[Type[BaseException]], _exc_val: Optional[BaseException], 
                 _exc_tb: Optional[TracebackType]) -> None:
        if self._start is not None:
            self.elapsed = time.time() - self._start
            self._start = None

def chunk_list(items: List[T], chunk_size: int) -> Iterator[List[T]]:
    """Split a list into chunks of specified size.
    
    Args:
        items: List to split into chunks
        chunk_size: Maximum size of each chunk
        
    Returns:
        Iterator yielding chunks of the list
    """
    for i in range(0, len(items), chunk_size):
        yield items[i:i + chunk_size]

class LRUCache:
    """Simple LRU cache implementation."""
    
    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self._cache: Dict[str, Any] = {}
        self._order: List[str] = []
        
    def get(self, key: str) -> Any:
        """Get item from cache."""
        if key not in self._cache:
            return None
        # Move to end (most recently used)
        self._order.remove(key)
        self._order.append(key)
        return self._cache[key]
        
    def put(self, key: str, value: Any) -> None:
        """Add item to cache."""
        if key in self._cache:
            self._order.remove(key)
        elif len(self._cache) >= self.capacity:
            # Remove least recently used
            lru = self._order.pop(0)
            del self._cache[lru]
        
        self._cache[key] = value
        self._order.append(key)
        
    def remove(self, key: str) -> None:
        """Remove item from cache."""
        if key in self._cache:
            del self._cache[key]
            self._order.remove(key)
            
    def keys(self) -> List[str]:
        """Get list of cache keys."""
        return list(self._cache.keys())
        
    def __len__(self) -> int:
        return len(self._cache)

def atomic_operation(func: F) -> F:
    """Decorator for atomic file operations."""
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # Log error and re-raise
            logger.error(f"Atomic operation failed: {str(e)}")
            raise
    return cast(F, wrapper)

__all__ = [
    'ThreadSafeSingleton',
    'safe_operation',
    'read_yaml_file',
    'read_json_file',
    'write_json_file',
    'ensure_directory',
    'cleanup',
    'Timer',
    'chunk_list',
    'LRUCache',
    'atomic_operation'
]
