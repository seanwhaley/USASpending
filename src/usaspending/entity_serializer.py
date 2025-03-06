"""Entity serialization system."""
from typing import Dict, Any, List, Optional, TypeVar, Generic, Type
import json
import csv
from io import StringIO
import dataclasses
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
import yaml

from .interfaces import IEntitySerializer
from .logging_config import get_logger

logger = get_logger(__name__)

T = TypeVar('T')

class SerializationError(Exception):
    """Error during entity serialization."""
    pass

class EntitySerializer(IEntitySerializer[T]):
    """Handles entity serialization to various formats."""
    
    def __init__(self, entity_class: Type[T]):
        """Initialize serializer for entity type."""
        self.entity_class = entity_class
        
    def to_dict(self, entity: T) -> Dict[str, Any]:
        """Convert entity to dictionary."""
        if dataclasses.is_dataclass(entity):
            return self._dataclass_to_dict(entity)
        return self._object_to_dict(entity)
        
    def from_dict(self, data: Dict[str, Any]) -> T:
        """Create entity from dictionary."""
        if dataclasses.is_dataclass(self.entity_class):
            return self._dict_to_dataclass(data)
        return self._dict_to_object(data)
        
    def to_json(self, entity: T) -> str:
        """Convert entity to JSON string."""
        data = self.to_dict(entity)
        try:
            return json.dumps(data, cls=EntityJSONEncoder)
        except Exception as e:
            raise SerializationError(f"JSON serialization failed: {str(e)}")
            
    def from_json(self, json_str: str) -> T:
        """Create entity from JSON string."""
        try:
            data = json.loads(json_str)
            return self.from_dict(data)
        except Exception as e:
            raise SerializationError(f"JSON deserialization failed: {str(e)}")
            
    def to_csv_row(self, entity: T) -> List[str]:
        """Convert entity to CSV row."""
        data = self.to_dict(entity)
        return [str(data.get(field, '')) for field in self._get_field_names()]
        
    def from_csv_row(self, row: List[str], headers: List[str]) -> T:
        """Create entity from CSV row."""
        if len(row) != len(headers):
            raise SerializationError(
                f"CSV row length ({len(row)}) does not match headers ({len(headers)})"
            )
            
        data = dict(zip(headers, row))
        return self.from_dict(data)
        
    def _dataclass_to_dict(self, entity: T) -> Dict[str, Any]:
        """Convert dataclass instance to dictionary."""
        try:
            return dataclasses.asdict(entity)
        except Exception as e:
            raise SerializationError(f"Dataclass serialization failed: {str(e)}")
            
    def _dict_to_dataclass(self, data: Dict[str, Any]) -> T:
        """Create dataclass instance from dictionary."""
        try:
            field_types = {
                field.name: field.type
                for field in dataclasses.fields(self.entity_class)
            }
            
            # Convert values to appropriate types
            converted_data = {}
            for key, value in data.items():
                if key in field_types:
                    converted_data[key] = self._convert_value(
                        value, field_types[key]
                    )
                    
            return self.entity_class(**converted_data)
            
        except Exception as e:
            raise SerializationError(
                f"Dataclass deserialization failed: {str(e)}"
            )
            
    def _object_to_dict(self, entity: T) -> Dict[str, Any]:
        """Convert object instance to dictionary."""
        try:
            return {
                key: value
                for key, value in vars(entity).items()
                if not key.startswith('_')
            }
        except Exception as e:
            raise SerializationError(f"Object serialization failed: {str(e)}")
            
    def _dict_to_object(self, data: Dict[str, Any]) -> T:
        """Create object instance from dictionary."""
        try:
            instance = self.entity_class()
            for key, value in data.items():
                if hasattr(instance, key):
                    setattr(instance, key, value)
            return instance
        except Exception as e:
            raise SerializationError(f"Object deserialization failed: {str(e)}")
            
    def _convert_value(self, value: Any, target_type: Type) -> Any:
        """Convert value to target type."""
        if value is None:
            return None
            
        # Handle optional types
        if hasattr(target_type, "__origin__") and target_type.__origin__ is Optional:
            target_type = target_type.__args__[0]
            
        # Basic type conversions
        if target_type == str:
            return str(value)
        elif target_type == int:
            return int(value)
        elif target_type == float:
            return float(value)
        elif target_type == bool:
            return bool(value)
        elif target_type == datetime:
            if isinstance(value, str):
                return datetime.fromisoformat(value)
            return value
        elif target_type == date:
            if isinstance(value, str):
                return datetime.fromisoformat(value).date()
            return value
        elif target_type == Decimal:
            return Decimal(str(value))
        elif issubclass(target_type, Enum):
            return target_type(value)
            
        return value
        
    def _get_field_names(self) -> List[str]:
        """Get field names for entity type."""
        if dataclasses.is_dataclass(self.entity_class):
            return [field.name for field in dataclasses.fields(self.entity_class)]
        
        # For regular objects, get public attributes
        sample = self.entity_class()
        return [
            attr for attr in dir(sample)
            if not attr.startswith('_') and not callable(getattr(sample, attr))
        ]

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
        elif dataclasses.is_dataclass(obj):
            return dataclasses.asdict(obj)
        return super().default(obj)

class YAMLEntitySerializer(EntitySerializer[T]):
    """Entity serializer with YAML support."""
    
    def to_yaml(self, entity: T) -> str:
        """Convert entity to YAML string."""
        data = self.to_dict(entity)
        try:
            return yaml.dump(data, sort_keys=False, default_flow_style=False)
        except Exception as e:
            raise SerializationError(f"YAML serialization failed: {str(e)}")
            
    def from_yaml(self, yaml_str: str) -> T:
        """Create entity from YAML string."""
        try:
            data = yaml.safe_load(yaml_str)
            return self.from_dict(data)
        except Exception as e:
            raise SerializationError(f"YAML deserialization failed: {str(e)}")

class CSVEntitySerializer(EntitySerializer[T]):
    """Enhanced CSV serializer for entities."""
    
    def __init__(self, entity_class: Type[T],
                 field_order: Optional[List[str]] = None,
                 delimiter: str = ',',
                 quotechar: str = '"'):
        """Initialize CSV serializer."""
        super().__init__(entity_class)
        self.field_order = field_order or self._get_field_names()
        self.delimiter = delimiter
        self.quotechar = quotechar
        
    def to_csv_string(self, entities: List[T]) -> str:
        """Convert multiple entities to CSV string."""
        output = StringIO()
        writer = csv.writer(
            output,
            delimiter=self.delimiter,
            quotechar=self.quotechar,
            quoting=csv.QUOTE_MINIMAL
        )
        
        # Write header
        writer.writerow(self.field_order)
        
        # Write data rows
        for entity in entities:
            writer.writerow(self.to_csv_row(entity))
            
        return output.getvalue()
        
    def from_csv_string(self, csv_str: str) -> List[T]:
        """Create multiple entities from CSV string."""
        input_file = StringIO(csv_str)
        reader = csv.reader(
            input_file,
            delimiter=self.delimiter,
            quotechar=self.quotechar
        )
        
        # Read header
        try:
            headers = next(reader)
        except StopIteration:
            raise SerializationError("Empty CSV data")
            
        # Read data rows
        entities = []
        for row in reader:
            entity = self.from_csv_row(row, headers)
            entities.append(entity)
            
        return entities