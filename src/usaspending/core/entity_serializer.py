"""Entity serialization core functionality.

This module provides serialization capabilities for entity objects to and from
various formats including JSON, YAML, CSV and Python dictionaries. It supports
both dataclass and regular class entities with automatic type conversion.

Key features:
- JSON serialization with custom type handling
- YAML serialization support
- CSV import/export with configurable field ordering
- Dictionary conversion for both dataclass and regular objects
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, TypeVar, Generic, Type, Optional, List, cast, Union
import json
import csv
from io import StringIO
import dataclasses
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
import yaml
from dataclasses import dataclass, is_dataclass, asdict

from .types import DataclassProtocol
from .interfaces import IEntitySerializer
from .exceptions import EntityError
from .logging_config import get_logger

logger = get_logger(__name__)

# Define EntityT as a TypeVar bound to DataclassProtocol
T = TypeVar('T', bound=DataclassProtocol)

class EntityJSONEncoder(json.JSONEncoder):
    """JSON encoder for entity types."""
    
    def default(self, obj: Any) -> Any:
        """Convert special types to JSON-serializable values."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, date):
            return obj.isoformat()
        elif isinstance(obj, Decimal):
            return str(obj)
        elif isinstance(obj, Enum):
            return obj.value
        elif is_dataclass(obj):
            # Only serialize actual instances, not the class itself
            if isinstance(obj, type):
                return str(obj)
            return dataclasses.asdict(obj)
        return super().default(obj)

class EntitySerializer(Generic[T]):
    def __init__(self, entity: T) -> None:
        self.entity = entity

    def to_dict(self) -> dict[str, Any]:
        return asdict(cast(Any, self.entity))

    def from_dict(self, data: dict[str, Any]) -> T:
        # Convert dictionary back to entity type
        # This assumes self.entity has a way to update from dict
        for key, value in data.items():
            setattr(self.entity, key, value)
        return self.entity

    @classmethod
    def create(cls, entity_cls: Type[T]) -> 'EntitySerializer[T]':
        # Create a new instance of the entity class
        instance = entity_cls()
        return cls(instance)

    @classmethod
    def serialize(cls, entity: T) -> dict[str, Any]:
        return cls(entity).to_dict()

    @classmethod
    def deserialize(cls, entity_cls: Type[T], data: dict[str, Any]) -> T:
        serializer = cls.create(entity_cls)
        return serializer.from_dict(data)

class YAMLEntitySerializer(EntitySerializer[T]):
    """Entity serializer with YAML support."""
    
    def to_yaml(self) -> str:
        """Convert entity to YAML string."""
        try:
            data = self.to_dict()
            result = yaml.dump(data, sort_keys=False)
            return result
        except Exception as e:
            raise EntityError(f"YAML serialization failed: {str(e)}")
    
    def from_yaml(self, yaml_str: str) -> T:
        """Create entity from YAML string."""
        try:
            data = yaml.safe_load(yaml_str)
            if not isinstance(data, dict):
                raise ValueError("YAML must deserialize to a dictionary")
            return self.from_dict(data)
        except Exception as e:
            raise EntityError(f"YAML deserialization failed: {str(e)}")

class CSVEntitySerializer(EntitySerializer[T]):
    """Enhanced CSV serializer for entities."""
    
    def __init__(self, entity_class: Type[T], field_order: Optional[List[str]] = None):
        """Initialize CSV serializer."""
        instance = entity_class()  # Create instance from class
        super().__init__(instance)
        self.field_order = field_order or []
        self.entity_class = entity_class  # Store class for creating new instances

    def to_csv(self, entities: List[T], include_headers: bool = True) -> str:
        """Convert entities to CSV string."""
        output = StringIO()
        writer = csv.writer(output)
        
        # Write headers if requested
        if include_headers and entities:
            headers = self.field_order or self._get_field_names(entities[0])
            writer.writerow(headers)
            
        # Write data rows
        for entity in entities:
            row = self._entity_to_row(entity)
            writer.writerow(row)
            
        return output.getvalue()
    
    def from_csv(self, csv_data: str) -> List[T]:
        """Create entities from CSV string."""
        reader = csv.reader(StringIO(csv_data))
        headers = next(reader)  # Get headers
        
        entities = []
        for row in reader:
            entity_dict = dict(zip(headers, row))
            entities.append(self.from_dict(entity_dict))
            
        return entities
    
    def _get_field_names(self, entity: T) -> List[str]:
        """Get field names from entity."""
        if self.field_order:
            return self.field_order
        elif dataclasses.is_dataclass(entity):
            return [f.name for f in dataclasses.fields(entity)]
        return list(vars(entity).keys())
    
    def _entity_to_row(self, entity: T) -> List[str]:
        """Convert entity to CSV row."""
        self.entity = entity  # Update current entity
        data = self.to_dict()  # Use self.to_dict() without arguments
        field_names = self.field_order or self._get_field_names(entity)
        return [str(data.get(field, "")) for field in field_names]

__all__ = [
    'EntitySerializer',
    'YAMLEntitySerializer',
    'CSVEntitySerializer'
]
