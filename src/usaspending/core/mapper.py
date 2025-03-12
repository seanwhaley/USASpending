"""Core mapping functionality."""
from typing import Dict, Any, Optional, List, Protocol, Union, TypedDict, cast
from dataclasses import dataclass, field
import logging
import re
from concurrent.futures import ThreadPoolExecutor, Future

from .exceptions import MappingError
from .utils import safe_operation

logger = logging.getLogger(__name__)

class MappingResult(TypedDict, total=False):
    """Result of an entity mapping operation."""
    entity_type: str
    data: Dict[str, Any]
    errors: List[str]

class FieldMapping(TypedDict, total=False):
    """Field mapping configuration."""
    source: Union[str, List[str], Dict[str, str]]
    target: str
    transforms: List[Dict[str, Any]]
    required: bool
    default: Any

class MappingConfig(TypedDict, total=False):
    """Configuration for entity mapping."""
    fields: List[FieldMapping]
    validation: Dict[str, Any]
    transforms: List[Dict[str, Any]]

class IEntityMapper(Protocol):
    """Interface for entity mapping."""
    
    def map_entity(self, entity_type: str, data: Dict[str, Any]) -> MappingResult:
        """Map entity data according to configuration."""
        ...
        
    def get_mapping_errors(self) -> List[str]:
        """Get mapping error messages."""
        ...
        
    def clear_errors(self) -> None:
        """Clear mapping errors."""
        ...

class BaseEntityMapper(IEntityMapper):
    """Base implementation of entity mapper."""
    
    def __init__(self) -> None:
        """Initialize base mapper."""
        self.errors: List[str] = []
        self._mapping_configs: Dict[str, MappingConfig] = {}
        self._enable_validation = True
        self._field_cache: Dict[str, Any] = {}
        
    def _get_field_value(self, data: Dict[str, Any], field_path: str) -> Optional[Any]:
        """Get field value using dot notation path."""
        if not field_path or not data:
            return None
            
        try:
            # Handle nested field paths
            parts = field_path.split('.')
            value: Any = data
            for part in parts:
                if isinstance(value, dict):
                    value = value.get(part)
                    if value is None:
                        return None
                else:
                    return None
            return value
            
        except Exception as e:
            logger.error(f"Field access error: {str(e)}")
            return None
            
    def _apply_transform(self, value: Any, transform: Dict[str, Any]) -> Any:
        """Apply transformation to a field value."""
        if not transform or value is None:
            return value
            
        try:
            transform_type = transform.get("type")
            if transform_type is None:
                return value
            
            if transform_type == "string":
                return str(value)
            elif transform_type == "integer":
                return int(float(value))
            elif transform_type == "float":
                return float(value)
            elif transform_type == "boolean":
                return bool(value)
            elif transform_type == "replace":
                pattern = transform.get("pattern")
                replacement = transform.get("replacement", "")
                if pattern:
                    return re.sub(pattern, replacement, str(value))
            elif transform_type == "format":
                format_str = transform.get("format")
                if format_str:
                    return format_str.format(value=value)
            elif transform_type == "map":
                mapping = transform.get("mapping", {})
                return mapping.get(value, value)
                    
            return value
            
        except Exception as e:
            logger.error(f"Transform failed: {str(e)}")
            return value
            
    def _map_field(self, data: Dict[str, Any], mapping: FieldMapping) -> Optional[Any]:
        """Map a single field according to configuration."""
        try:
            source = mapping.get("source")
            transforms = mapping.get("transforms", [])
            
            # Handle different source types
            value: Optional[Any] = None
            if isinstance(source, str):
                value = self._get_field_value(data, source)
            elif isinstance(source, list):
                # Multi-source field mapping
                for src in source:
                    value = self._get_field_value(data, src)
                    if value is not None:
                        break
            elif isinstance(source, dict):
                # Object mapping
                value = {}
                for key, src in source.items():
                    field_value = self._get_field_value(data, src)
                    if field_value is not None:
                        value[key] = field_value
                        
            # Apply transformations in sequence
            for transform in transforms:
                value = self._apply_transform(value, transform)
                
            return value
            
        except Exception as e:
            logger.error(f"Field mapping failed: {str(e)}")
            return None

    def register_mapping(self, entity_type: str, config: MappingConfig) -> None:
        """Register a mapping configuration."""
        if not entity_type or not config:
            raise MappingError("Entity type and mapping config required")
        self._mapping_configs[entity_type] = config

    def get_mapping_config(self, entity_type: str) -> Optional[MappingConfig]:
        """Get mapping configuration for entity type."""
        return self._mapping_configs.get(entity_type)

    def clear_cache(self) -> None:
        """Clear field value cache."""
        self._field_cache.clear()

    def map_entity(self, entity_type: str, data: Dict[str, Any]) -> MappingResult:
        """Map entity data according to configuration."""
        if not entity_type or not data:
            self.errors.append("Entity type and data are required")
            return MappingResult(entity_type=entity_type, data={}, errors=self.errors.copy())
            
        config = self._mapping_configs.get(entity_type)
        if not config:
            logger.warning(f"No mapping config for type: {entity_type}")
            return MappingResult(entity_type=entity_type, data=data, errors=[])
            
        try:
            result: Dict[str, Any] = {}
            field_maps = config.get("fields", [])
            for field_map in field_maps:
                target = field_map.get("target")
                if target:
                    value = self._map_field(data, field_map)
                    if value is not None:
                        # Handle nested field paths
                        parts = target.split('.')
                        current = result
                        for part in parts[:-1]:
                            current = current.setdefault(part, {})
                        current[parts[-1]] = value
                        
            return MappingResult(entity_type=entity_type, data=result, errors=self.errors.copy())
            
        except Exception as e:
            self.errors.append(f"Entity mapping failed: {str(e)}")
            return MappingResult(entity_type=entity_type, data={}, errors=self.errors.copy())

    def get_mapping_errors(self) -> List[str]:
        """Get mapping error messages."""
        return self.errors.copy()
        
    def clear_errors(self) -> None:
        """Clear mapping errors."""
        self.errors.clear()

class ParallelEntityMapper(BaseEntityMapper):
    """Entity mapper with parallel field processing."""
    
    def __init__(self, max_workers: int = 4) -> None:
        """Initialize parallel mapper."""
        super().__init__()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        
    @safe_operation
    def map_entity(self, entity_type: str, data: Dict[str, Any]) -> MappingResult:
        """Map entity data with parallel field processing."""
        if not entity_type or not data:
            self.errors.append("Entity type and data are required")
            return MappingResult(entity_type=entity_type, data={}, errors=self.errors.copy())
            
        config = self._mapping_configs.get(entity_type)
        if not config:
            logger.warning(f"No mapping config for type: {entity_type}")
            return MappingResult(entity_type=entity_type, data=data, errors=[])
            
        try:
            result: Dict[str, Any] = {}
            futures: List[tuple[str, Future[Optional[Any]]]] = []
            field_maps = config.get("fields", [])
            
            # Process field mappings in parallel
            for field_map in field_maps:
                target = field_map.get("target")
                if target:
                    future = self._executor.submit(self._map_field, data, field_map)
                    futures.append((target, future))
                    
            # Collect mapping results
            for target, future in futures:
                try:
                    value = future.result()
                    if value is not None:
                        # Handle nested field paths
                        parts = target.split('.')
                        current = result
                        for part in parts[:-1]:
                            current = current.setdefault(part, {})
                        current[parts[-1]] = value
                        
                except Exception as e:
                    self.errors.append(f"Mapping failed for {target}: {str(e)}")
                    
            return MappingResult(entity_type=entity_type, data=result, errors=self.errors.copy())
            
        except Exception as e:
            self.errors.append(f"Entity mapping failed: {str(e)}")
            return MappingResult(entity_type=entity_type, data={}, errors=self.errors.copy())

    def cleanup(self) -> None:
        """Clean up resources."""
        self._executor.shutdown()
        self.clear_cache()

@dataclass
class FieldTransform:
    """Field transformation configuration."""
    type: str
    parameters: Dict[str, Any] = field(default_factory=dict)

@dataclass
class FieldMappingConfig:
    """Field mapping configuration."""
    source: Union[str, List[str], Dict[str, str]]
    target: str
    transforms: List[FieldTransform] = field(default_factory=list)
    required: bool = False
    default: Any = None

__all__ = [
    'IEntityMapper',
    'BaseEntityMapper',
    'ParallelEntityMapper',
    'FieldTransform',
    'FieldMappingConfig',
    'MappingResult',
    'MappingConfig'
]