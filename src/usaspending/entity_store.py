"""Entity storage system for persisting entities."""
from typing import Dict, Any, List, Optional, TypeVar, Generic, Iterator
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import json
import os
import threading
from datetime import datetime
import sqlite3
from contextlib import contextmanager

from .interfaces import IEntityFactory
from .logging_config import get_logger

logger = get_logger(__name__)

T = TypeVar('T')

class IEntityStore(ABC, Generic[T]):
    """Interface for entity storage systems."""
    
    @abstractmethod
    def save(self, entity_type: str, entity: T) -> str:
        """Save entity and return its ID."""
        pass
    
    @abstractmethod
    def get(self, entity_type: str, entity_id: str) -> Optional[T]:
        """Get entity by ID."""
        pass
    
    @abstractmethod
    def delete(self, entity_type: str, entity_id: str) -> bool:
        """Delete entity by ID."""
        pass
    
    @abstractmethod
    def list(self, entity_type: str) -> Iterator[T]:
        """List all entities of a type."""
        pass
    
    @abstractmethod
    def count(self, entity_type: str) -> int:
        """Count entities of a type."""
        pass

class SQLiteEntityStore(IEntityStore[T]):
    """SQLite-based entity storage implementation."""
    
    def __init__(self, db_path: str, factory: IEntityFactory):
        """Initialize store with database path and entity factory."""
        self.db_path = db_path
        self.factory = factory
        self._lock = threading.RLock()
        self._init_db()
        
    @contextmanager
    def _get_connection(self):
        """Get database connection context."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
            finally:
                conn.close()
                
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

class FileSystemEntityStore(IEntityStore[T]):
    """File system-based entity storage implementation."""
    
    def __init__(self, base_path: str, factory: IEntityFactory):
        """Initialize store with base path and entity factory."""
        self.base_path = base_path
        self.factory = factory
        self._lock = threading.RLock()
        os.makedirs(base_path, exist_ok=True)
        
    def _get_type_path(self, entity_type: str) -> str:
        """Get path for entity type storage."""
        return os.path.join(self.base_path, entity_type)
        
    def _get_entity_path(self, entity_type: str, entity_id: str) -> str:
        """Get path for specific entity."""
        return os.path.join(self._get_type_path(entity_type), f"{entity_id}.json")
        
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
            
            # Ensure type directory exists
            type_path = self._get_type_path(entity_type)
            os.makedirs(type_path, exist_ok=True)
            
            # Save entity file
            entity_path = self._get_entity_path(entity_type, entity_id)
            with open(entity_path, 'w') as f:
                json.dump(data, f, indent=2)
                
        return entity_id
        
    def get(self, entity_type: str, entity_id: str) -> Optional[T]:
        """Get entity by ID."""
        entity_path = self._get_entity_path(entity_type, entity_id)
        
        try:
            with open(entity_path, 'r') as f:
                data = json.load(f)
            return self.factory.create_entity(entity_type, data)
        except FileNotFoundError:
            return None
            
    def delete(self, entity_type: str, entity_id: str) -> bool:
        """Delete entity by ID."""
        entity_path = self._get_entity_path(entity_type, entity_id)
        
        try:
            os.remove(entity_path)
            return True
        except FileNotFoundError:
            return False
            
    def list(self, entity_type: str) -> Iterator[T]:
        """List all entities of a type."""
        type_path = self._get_type_path(entity_type)
        
        try:
            for filename in os.listdir(type_path):
                if filename.endswith('.json'):
                    entity_id = filename[:-5]  # Remove .json
                    entity = self.get(entity_type, entity_id)
                    if entity:
                        yield entity
        except FileNotFoundError:
            return
            
    def count(self, entity_type: str) -> int:
        """Count entities of a type."""
        type_path = self._get_type_path(entity_type)
        
        try:
            return len([f for f in os.listdir(type_path) if f.endswith('.json')])
        except FileNotFoundError:
            return 0
            
    def _generate_id(self, entity_type: str) -> str:
        """Generate unique entity ID."""
        import uuid
        return f"{entity_type}-{uuid.uuid4()}"

class EntityStoreBuilder:
    """Builder for creating configured EntityStore instances."""
    
    def __init__(self):
        """Initialize builder."""
        self.storage_type: str = 'sqlite'
        self.path: str = ':memory:'
        self.factory: Optional[IEntityFactory] = None
        
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
        
    def build(self) -> IEntityStore:
        """Create EntityStore instance."""
        if not self.factory:
            raise ValueError("Entity factory is required")
            
        if self.storage_type == 'sqlite':
            return SQLiteEntityStore(self.path, self.factory)
        elif self.storage_type == 'filesystem':
            return FileSystemEntityStore(self.path, self.factory)
        else:
            raise ValueError(f"Unknown storage type: {self.storage_type}")