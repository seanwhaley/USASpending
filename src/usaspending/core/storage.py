"""Storage implementations for entity persistence."""
from typing import Dict, Any, Optional, List, Protocol, Generator, TypeVar, Generic, cast
from abc import abstractmethod
import os
import json
import sqlite3
from pathlib import Path
from contextlib import contextmanager

from .types import EntityData
from .exceptions import StorageError

T = TypeVar('T', bound=Dict[str, Any])

class IStorageStrategy(Protocol, Generic[T]):
    """Storage strategy interface."""
    
    @abstractmethod
    def save_entity(self, entity_type: str, entity: T) -> str:
        """Save an entity and return its ID."""
        ...
        
    @abstractmethod
    def get_entity(self, entity_type: str, entity_id: str) -> Optional[T]:
        """Get an entity by ID."""
        ...
        
    @abstractmethod
    def delete_entity(self, entity_type: str, entity_id: str) -> bool:
        """Delete an entity."""
        ...
        
    @abstractmethod
    def list_entities(self, entity_type: str) -> Generator[T, None, None]:
        """Stream entities of a type."""
        ...
        
    @abstractmethod
    def count_entities(self, entity_type: str) -> int:
        """Count entities of a type."""
        ...
        
    @abstractmethod
    def cleanup(self) -> None:
        """Clean up resources."""
        ...

class SQLiteStorage(IStorageStrategy[Dict[str, Any]]):
    """SQLite-based entity storage."""
    
    def __init__(self, db_path: str, max_connections: int = 5):
        self.db_path = db_path
        self.max_connections = max_connections
        self._conn_pool: List[sqlite3.Connection] = []
        self._initialize_db()
        
    @contextmanager
    def get_connection_context(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a managed database connection context."""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._return_connection(conn)
            
    def _initialize_db(self) -> None:
        """Initialize database and tables."""
        with self.get_connection_context() as conn:
            conn.execute("""    
                CREATE TABLE IF NOT EXISTS entities (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_type ON entities(type)")
        
    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        if not self._conn_pool:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn
            
        return self._conn_pool.pop()
        
    def _return_connection(self, conn: sqlite3.Connection) -> None:
        """Return a connection to the pool."""
        if len(self._conn_pool) < self.max_connections:
            self._conn_pool.append(conn)
        else:
            conn.close()
    
    def save_entity(self, entity_type: str, entity: Dict[str, Any]) -> str:
        """Save an entity."""
        entity_id = str(hash(json.dumps(entity, sort_keys=True)))
        
        with self.get_connection_context() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO entities (id, type, data) VALUES (?, ?, ?)",
                (entity_id, entity_type, json.dumps(entity))
            )
            
        return entity_id
    
    def get_entity(self, entity_type: str, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get an entity by ID."""
        with self.get_connection_context() as conn:
            row = conn.execute(   
                "SELECT data FROM entities WHERE type = ? AND id = ?",
                (entity_type, entity_id)
            ).fetchone()
            
        if row:
            try:
                return cast(Dict[str, Any], json.loads(row[0]))
            except json.JSONDecodeError:
                raise StorageError(f"Invalid JSON data for entity {entity_id}")
        return None
        
    def delete_entity(self, entity_type: str, entity_id: str) -> bool:
        """Delete an entity."""
        with self.get_connection_context() as conn:
            cursor = conn.execute(
                "DELETE FROM entities WHERE type = ? AND id = ?",
                (entity_type, entity_id)
            )
            return cursor.rowcount > 0
        
    def list_entities(self, entity_type: str) -> Generator[Dict[str, Any], None, None]:
        """Stream entities of a type."""
        with self.get_connection_context() as conn:
            cursor = conn.execute(
                "SELECT data FROM entities WHERE type = ?",
                (entity_type,)
            )
            
            for row in cursor:
                try:
                    entity = json.loads(row[0])
                    yield cast(Dict[str, Any], entity)
                except json.JSONDecodeError:
                    continue  # Skip invalid entities but continue processing
        
    def count_entities(self, entity_type: str) -> int:
        """Count entities of a type."""
        with self.get_connection_context() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM entities WHERE type = ?",
                (entity_type,)
            ).fetchone()
            
        return row[0] if row else 0

    def cleanup(self) -> None:
        """Clean up resources."""    
        for conn in self._conn_pool:
            conn.close()
        self._conn_pool.clear()

class FileSystemStorage(IStorageStrategy[Dict[str, Any]]):
    """File system based entity storage."""
    
    def __init__(self, base_path: str, max_files_per_dir: int = 1000, compression: bool = True):
        self.base_path = Path(base_path)
        self.max_files_per_dir = max_files_per_dir
        self.compression = compression
        self._ensure_base_dir()
        
    def _ensure_base_dir(self) -> None:
        """Ensure base directory exists."""
        self.base_path.mkdir(parents=True, exist_ok=True)
        
    def _get_entity_path(self, entity_type: str, entity_id: str) -> Path:
        """Get path for entity file."""
        type_dir = self.base_path / entity_type
        shard = str(hash(entity_id) % self.max_files_per_dir)
        shard_dir = type_dir / shard
        shard_dir.mkdir(parents=True, exist_ok=True)
        return shard_dir / f"{entity_id}.json"
        
    def save_entity(self, entity_type: str, entity: Dict[str, Any]) -> str:
        """Save an entity."""
        entity_id = str(hash(json.dumps(entity, sort_keys=True)))
        path = self._get_entity_path(entity_type, entity_id)
        
        with open(path, 'w') as f:
            json.dump(entity, f)
            
        return entity_id
        
    def get_entity(self, entity_type: str, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get an entity by ID."""
        path = self._get_entity_path(entity_type, entity_id)
        
        if path.exists():
            try:
                with open(path) as f:
                    return cast(Dict[str, Any], json.load(f))
            except json.JSONDecodeError:
                raise StorageError(f"Invalid JSON data for entity {entity_id}")
        return None
        
    def delete_entity(self, entity_type: str, entity_id: str) -> bool:
        """Delete an entity."""
        path = self._get_entity_path(entity_type, entity_id)
        
        try:
            path.unlink()
            return True
        except FileNotFoundError:
            return False
            
    def list_entities(self, entity_type: str) -> Generator[Dict[str, Any], None, None]:
        """Stream entities of a type."""
        type_dir = self.base_path / entity_type
        if not type_dir.exists():
            return
            
        for shard_dir in type_dir.iterdir():
            if shard_dir.is_dir():
                for path in shard_dir.glob("*.json"):
                    try:
                        with open(path) as f:
                            entity = json.load(f)
                            yield cast(Dict[str, Any], entity)
                    except json.JSONDecodeError:
                        continue  # Skip invalid entities but continue processing
        
    def count_entities(self, entity_type: str) -> int:
        """Count entities of a type."""
        type_dir = self.base_path / entity_type
        if not type_dir.exists():
            return 0
            
        count = 0
        for shard_dir in type_dir.iterdir():
            if shard_dir.is_dir():
                count += len(list(shard_dir.glob("*.json")))
                
        return count
        
    def cleanup(self) -> None:
        """Clean up resources."""
        # No cleanup needed for file system storage
        pass

__all__ = [
    'IStorageStrategy',
    'SQLiteStorage',
    'FileSystemStorage'
]