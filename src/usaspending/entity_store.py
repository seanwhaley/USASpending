"""Entity storage system for persisting entities."""
from typing import Dict, Any, List, Optional, TypeVar, Generic, Iterator, Iterable
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import json
import os
import threading
import time
from datetime import datetime
import sqlite3
from contextlib import contextmanager
import gzip
import shutil
import pathlib
from concurrent.futures import ThreadPoolExecutor

from . import get_logger, ConfigurationError
from .interfaces import IEntityStore, IEntityFactory
from .component_utils import implements

logger = get_logger(__name__)

T = TypeVar('T')

@implements(IEntityStore)
class SQLiteEntityStore(IEntityStore[T]):
    """SQLite-based entity storage implementation."""
    
    def __init__(self, db_path: str, factory: IEntityFactory):
        """Initialize store with database path and entity factory."""
        self.db_path = db_path
        self.factory = factory
        self._lock = threading.RLock()
        self._pool: Optional[List[sqlite3.Connection]] = None
        self._pool_lock = threading.Lock()
        self._available_conns: List[int] = []
        self._journal_mode = 'WAL'
        self._pool_size = 1
        self._timeout_seconds = 30
        self._init_db()
        
    def configure_connection_pool(self, pool_size: int = 1, timeout_seconds: int = 30, journal_mode: str = 'WAL') -> None:
        """Configure the connection pool settings.
        
        Args:
            pool_size: Number of connections to maintain
            timeout_seconds: Connection timeout in seconds
            journal_mode: SQLite journal mode (WAL, DELETE, etc.)
        """
        with self._lock:
            # Close existing pool if it exists
            if self._pool:
                for conn in self._pool:
                    try:
                        conn.close()
                    except Exception:
                        pass
                        
            self._pool_size = max(1, pool_size)
            self._timeout_seconds = max(1, timeout_seconds)
            self._journal_mode = journal_mode.upper()
            
            # Initialize new connection pool
            self._pool = []
            self._available_conns = list(range(self._pool_size))
            
            for _ in range(self._pool_size):
                conn = self._create_connection()
                self._pool.append(conn)
    
    def _create_connection(self) -> sqlite3.Connection:
        """Create a new database connection with configured settings."""
        conn = sqlite3.connect(self.db_path, timeout=self._timeout_seconds)
        conn.row_factory = sqlite3.Row
        
        # Configure journal mode
        if self._journal_mode:
            conn.execute(f"PRAGMA journal_mode={self._journal_mode}")
            
        # Other pragmas for better performance
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-2000")  # 2MB cache
        
        return conn
    
    @contextmanager
    def _get_connection(self):
        """Get a connection from the pool."""
        if not self._pool:
            # No pool configured, use basic connection
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
            finally:
                conn.close()
            return
            
        # Get connection from pool
        conn_id = None
        try:
            with self._pool_lock:
                while not self._available_conns:
                    self._pool_lock.release()
                    time.sleep(0.1)  # Wait for available connection
                    self._pool_lock.acquire()
                conn_id = self._available_conns.pop()
                conn = self._pool[conn_id]
                
            yield conn
            
        finally:
            if conn_id is not None:
                with self._pool_lock:
                    self._available_conns.append(conn_id)
    
    def close(self) -> None:
        """Close all connections in the pool."""
        if self._pool:
            with self._lock:
                for conn in self._pool:
                    try:
                        conn.close()
                    except Exception:
                        pass
                self._pool = None
                self._available_conns = []

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS entities (
                    id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_entity_type 
                ON entities(entity_type)
            """)
            conn.commit()
            
    def save(self, entity_type: str, entity: T) -> str:
        """Save entity and return its ID."""
        # Convert entity to dictionary
        if hasattr(entity, '__dict__'):
            data = entity.__dict__
        elif hasattr(entity, '_asdict'):
            data = entity._asdict()
        else:
            data = dict(entity)
            
        # Generate ID if not present
        entity_id = data.get('id') or self._generate_id(entity_type)
        data['id'] = entity_id
        
        current_time = datetime.utcnow().isoformat()
        
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO entities 
                (id, entity_type, data, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                entity_id,
                entity_type,
                json.dumps(data),
                current_time,
                current_time
            ))
            conn.commit()
            
        return entity_id
        
    def get(self, entity_type: str, entity_id: str) -> Optional[T]:
        """Get entity by ID."""
        with self._get_connection() as conn:
            row = conn.execute("""
                SELECT data FROM entities 
                WHERE entity_type = ? AND id = ?
            """, (entity_type, entity_id)).fetchone()
            
        if not row:
            return None
            
        data = json.loads(row['data'])
        return self.factory.create_entity(entity_type, data)
        
    def delete(self, entity_type: str, entity_id: str) -> bool:
        """Delete entity by ID."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                DELETE FROM entities 
                WHERE entity_type = ? AND id = ?
            """, (entity_type, entity_id))
            conn.commit()
            
        return cursor.rowcount > 0
        
    def list(self, entity_type: str) -> Iterator[T]:
        """List all entities of a type."""
        with self._get_connection() as conn:
            for row in conn.execute("""
                SELECT data FROM entities 
                WHERE entity_type = ?
                ORDER BY created_at
            """, (entity_type,)):
                data = json.loads(row['data'])
                entity = self.factory.create_entity(entity_type, data)
                if entity:
                    yield entity
                    
    def count(self, entity_type: str) -> int:
        """Count entities of a type."""
        with self._get_connection() as conn:
            result = conn.execute("""
                SELECT COUNT(*) as count FROM entities 
                WHERE entity_type = ?
            """, (entity_type,)).fetchone()
            
        return result['count'] if result else 0
        
    def _generate_id(self, entity_type: str) -> str:
        """Generate unique entity ID."""
        import uuid
        return f"{entity_type}-{uuid.uuid4()}"

@implements(IEntityStore)
class FileSystemEntityStore(IEntityStore[T]):
    """File system-based entity storage implementation."""
    
    def __init__(self, base_path: str, factory: IEntityFactory, max_files_per_dir: int = 1000, compression: bool = True):
        """Initialize store with base path and entity factory.
        
        Args:
            base_path: Base directory path for entity storage
            factory: Factory for creating entity instances
            max_files_per_dir: Maximum number of files per subdirectory
            compression: Whether to use gzip compression
        """
        self.base_path = pathlib.Path(base_path)
        self.factory = factory
        self.max_files_per_dir = max_files_per_dir
        self.compression = compression
        self._lock = threading.RLock()
        self._type_counts: Dict[str, int] = {}
        self._ensure_base_dir()
        
        # Log the base directory path to verify it's correct
        logger.info(f"Entity store initialized with base path: {os.path.abspath(self.base_path)}")
    
    def _ensure_base_dir(self) -> None:
        """Ensure base directory exists."""
        try:
            os.makedirs(self.base_path, exist_ok=True)
            # Verify directory exists after creation
            if not os.path.exists(self.base_path):
                logger.error(f"Failed to create base directory: {self.base_path}")
            else:
                # Test write permissions
                test_file = self.base_path / "write_test.tmp"
                try:
                    with open(test_file, 'w') as f:
                        f.write("test")
                    os.remove(test_file)
                except Exception as e:
                    logger.error(f"Base directory exists but is not writable: {self.base_path}: {str(e)}")
        except Exception as e:
            logger.error(f"Error creating base directory: {self.base_path}: {str(e)}")
    
    def _get_type_dir(self, entity_type: str, create: bool = True) -> pathlib.Path:
        """Get directory path for entity type."""
        type_dir = self.base_path / entity_type
        if create:
            try:
                os.makedirs(type_dir, exist_ok=True)
                # Verify directory exists after creation
                if not os.path.exists(type_dir):
                    logger.error(f"Failed to create entity type directory: {type_dir}")
            except Exception as e:
                logger.error(f"Error creating entity type directory: {type_dir}: {str(e)}")
        return type_dir
    
    def _get_subdir_path(self, entity_type: str, entity_id: str) -> pathlib.Path:
        """Get subdirectory path for entity, creating parent dirs if needed."""
        # Use first few chars of ID for subdir to avoid too many files in one dir
        subdir_name = entity_id[:3] if len(entity_id) > 3 else entity_id
        subdir_path = self._get_type_dir(entity_type) / subdir_name
        try:
            os.makedirs(subdir_path, exist_ok=True)
            # Verify directory exists after creation
            if not os.path.exists(subdir_path):
                logger.error(f"Failed to create entity subdirectory: {subdir_path}")
        except Exception as e:
            logger.error(f"Error creating entity subdirectory: {subdir_path}: {str(e)}")
        return subdir_path
    
    def _get_entity_path(self, entity_type: str, entity_id: str) -> pathlib.Path:
        """Get full path for entity file."""
        subdir = self._get_subdir_path(entity_type, entity_id)
        filename = f"{entity_id}.json{'.gz' if self.compression else ''}"
        return subdir / filename
    
    def _generate_id(self, entity_type: str) -> str:
        """Generate unique entity ID."""
        import uuid
        return f"{entity_type}-{uuid.uuid4()}"
    
    def save(self, entity_type: str, entity: T) -> str:
        """Save entity and return its ID."""
        with self._lock:
            # Convert entity to dictionary
            if hasattr(entity, '__dict__'):
                data = entity.__dict__
            elif hasattr(entity, '_asdict'):
                data = entity._asdict()
            else:
                data = dict(entity)
                
            # Generate ID if not present
            entity_id = data.get('id') or self._generate_id(entity_type)
            data['id'] = entity_id
            
            # Add metadata
            current_time = datetime.utcnow().isoformat()
            data['_metadata'] = {
                'created_at': current_time,
                'updated_at': current_time,
                'entity_type': entity_type
            }
            
            # Get file path and ensure parent directory exists
            file_path = self._get_entity_path(entity_type, entity_id)
            
            # Write entity data
            try:
                # Prepare JSON content before opening file
                json_content = json.dumps(data, indent=2)
                
                # Ensure parent directory exists again right before writing
                os.makedirs(file_path.parent, exist_ok=True)
                
                if self.compression:
                    with gzip.open(file_path, 'wt', encoding='utf-8') as f:
                        f.write(json_content)
                else:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(json_content)
                        
                # Update type counts cache
                self._type_counts[entity_type] = -1  # Invalidate count
                
                # Log successful entity save
                logger.debug(f"Successfully saved entity {entity_type}/{entity_id} to {file_path}")
                
                return entity_id
                
            except Exception as e:
                logger.error(f"Error saving entity {entity_id} to {file_path}: {str(e)}")
                raise
    
    def get(self, entity_type: str, entity_id: str) -> Optional[T]:
        """Get entity by ID."""
        file_path = self._get_entity_path(entity_type, entity_id)
        
        try:
            if not file_path.exists():
                return None
                
            if self.compression:
                with gzip.open(file_path, 'rt', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
            return self.factory.create_entity(entity_type, data)
            
        except Exception as e:
            logger.error(f"Error loading entity {entity_id}: {str(e)}")
            return None
    
    def delete(self, entity_type: str, entity_id: str) -> bool:
        """Delete entity by ID."""
        with self._lock:
            file_path = self._get_entity_path(entity_type, entity_id)
            
            try:
                if file_path.exists():
                    os.remove(file_path)
                    
                    # Try to remove empty parent directories
                    parent = file_path.parent
                    while parent != self.base_path:
                        try:
                            parent.rmdir()  # Only removes if empty
                            parent = parent.parent
                        except OSError:
                            break
                            
                    # Invalidate type count
                    self._type_counts[entity_type] = -1
                    return True
                    
                return False
                
            except Exception as e:
                logger.error(f"Error deleting entity {entity_id}: {str(e)}")
                return False
    
    def list(self, entity_type: str) -> Iterator[T]:
        """List all entities of a type."""
        type_dir = self._get_type_dir(entity_type, create=False)
        
        if not type_dir.exists():
            return
            
        # Walk through all subdirectories
        for root, _, files in os.walk(type_dir):
            for filename in files:
                if not filename.endswith('.json' + ('.gz' if self.compression else '')):
                    continue
                    
                file_path = pathlib.Path(root) / filename
                
                try:
                    if self.compression:
                        with gzip.open(file_path, 'rt', encoding='utf-8') as f:
                            data = json.load(f)
                    else:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            
                    entity = self.factory.create_entity(entity_type, data)
                    if entity:
                        yield entity
                        
                except Exception as e:
                    logger.error(f"Error loading entity from {file_path}: {str(e)}")
                    continue
    
    def count(self, entity_type: str) -> int:
        """Count entities of a type."""
        # Check cache first
        if entity_type in self._type_counts and self._type_counts[entity_type] >= 0:
            return self._type_counts[entity_type]
            
        type_dir = self._get_type_dir(entity_type, create=False)
        
        if not type_dir.exists():
            return 0
            
        # Count all JSON/GZ files
        count = 0
        suffix = '.json' + ('.gz' if self.compression else '')
        
        for root, _, files in os.walk(type_dir):
            count += sum(1 for f in files if f.endswith(suffix))
            
        # Cache the result
        self._type_counts[entity_type] = count
        return count
    
    def _cleanup_empty_dirs(self) -> None:
        """Remove empty subdirectories."""
        with self._lock:
            for root, dirs, files in os.walk(self.base_path, topdown=False):
                for dirname in dirs:
                    try:
                        dir_path = pathlib.Path(root) / dirname
                        dir_path.rmdir()  # Only removes if empty
                    except OSError:
                        continue

class EntityStoreBuilder:
    """Builder for creating configured EntityStore instances."""
    
    def __init__(self):
        """Initialize builder."""
        self.storage_type: str = 'sqlite'
        self.path: str = ':memory:'
        self.factory: Optional[IEntityFactory] = None
        self.max_files_per_dir: int = 1000
        self.compression: bool = True
        self.pool_size: int = 1
        self.timeout_seconds: int = 30
        self.journal_mode: str = 'WAL'
        
    def with_sqlite_storage(self, db_path: str) -> 'EntityStoreBuilder':
        """Use SQLite storage."""
        self.storage_type = 'sqlite'
        self.path = db_path
        return self
        
    def with_filesystem_storage(self, base_path: str) -> 'EntityStoreBuilder':
        """Use file system storage."""
        self.storage_type = 'filesystem'
        self.path = base_path
        return self
        
    def with_factory(self, factory: IEntityFactory) -> 'EntityStoreBuilder':
        """Set entity factory."""
        self.factory = factory
        return self
        
    def with_storage_options(self, **options) -> 'EntityStoreBuilder':
        """Set additional storage options."""
        if 'max_files_per_dir' in options:
            self.max_files_per_dir = options['max_files_per_dir']
        if 'compression' in options:
            self.compression = options['compression']
        if 'pool_size' in options:
            self.pool_size = options['pool_size']
        if 'timeout_seconds' in options:
            self.timeout_seconds = options['timeout_seconds']
        if 'journal_mode' in options:
            self.journal_mode = options['journal_mode']
        return self
        
    def from_config(self, config: Dict[str, Any]) -> 'EntityStoreBuilder':
        """Configure builder from configuration dictionary."""
        if not isinstance(config, dict):
            raise ValueError("Configuration must be a dictionary")
            
        storage_config = config.get('config', {})
        
        # Get storage type
        storage_type = storage_config.get('storage_type', 'sqlite')
        if storage_type not in ('sqlite', 'filesystem'):
            raise ValueError(f"Invalid storage type: {storage_type}")
            
        # Get path
        path = storage_config.get('path')
        if not path:
            raise ValueError("Storage path is required")
            
        # Configure storage type
        if storage_type == 'sqlite':
            self.with_sqlite_storage(path)
        else:
            self.with_filesystem_storage(path)
            
        # Configure storage options
        self.with_storage_options(
            max_files_per_dir=storage_config.get('max_files_per_dir', 1000),
            compression=storage_config.get('compression', True),
            pool_size=storage_config.get('pool_size', 1),
            timeout_seconds=storage_config.get('timeout_seconds', 30),
            journal_mode=storage_config.get('journal_mode', 'WAL')
        )
        
        return self
        
    def build(self) -> IEntityStore:
        """Create EntityStore instance."""
        if not self.factory:
            raise ValueError("Entity factory is required")
            
        if self.storage_type == 'sqlite':
            store = SQLiteEntityStore(self.path, self.factory)
            # Configure SQLite connection pool and journal mode if supported
            if hasattr(store, 'configure_connection_pool'):
                store.configure_connection_pool(
                    pool_size=self.pool_size,
                    timeout_seconds=self.timeout_seconds,
                    journal_mode=self.journal_mode
                )
            return store
        elif self.storage_type == 'filesystem':
            return FileSystemEntityStore(
                self.path,
                self.factory,
                max_files_per_dir=self.max_files_per_dir,
                compression=self.compression
            )
        else:
            raise ValueError(f"Unknown storage type: {self.storage_type}")

# Default store implementation
EntityStore = SQLiteEntityStore  # Use SQLite as the default implementation

# Factory method to create an instance from the configuration
def create_entity_store_from_config(config: Dict[str, Any], factory: Optional[IEntityFactory] = None) -> IEntityStore:
    """Create an EntityStore instance from configuration.
    
    Args:
        config: Configuration dictionary
        factory: Factory for creating entity instances (required)
        
    Returns:
        Configured entity store instance
        
    Raises:
        ValueError: If factory is not provided
    """
    if factory is None:
        raise ValueError("Entity factory must be provided")
        
    # Extract config from system.entity_store section if needed
    if isinstance(config, dict) and "config" in config:
        config = config["config"]
    
    # Get storage type and other configuration
    storage_type = config.get("storage_type", "filesystem")
    
    builder = EntityStoreBuilder().with_factory(factory)
    
    if storage_type == "filesystem":
        # Configure and return FileSystemEntityStore
        path = config.get("path", "output/entities")
        max_files = config.get("max_files_per_dir", 1000)
        compression = config.get("compression", True)
        
        return builder.with_filesystem_storage(path).with_storage_options(
            max_files_per_dir=max_files,
            compression=compression
        ).build()
        
    elif storage_type == "sqlite":
        # Configure and return SQLiteEntityStore
        db_path = config.get("path") or config.get("db_file", "output/entities.db")
        pool_size = config.get("pool_size", 1)
        timeout = config.get("timeout_seconds", 30)
        journal_mode = config.get("journal_mode", "WAL")
        
        return builder.with_sqlite_storage(db_path).with_storage_options(
            pool_size=pool_size,
            timeout_seconds=timeout,
            journal_mode=journal_mode
        ).build()
        
    else:
        raise ConfigurationError(f"Unknown entity storage type: {storage_type}")