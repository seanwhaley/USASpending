"""Entity mapping functionality."""
from typing import Dict, Any, Optional, List, Set
from .validation_base import BaseValidator
from .text_file_cache import TextFileCache
from .exceptions import EntityMappingError
from .logging_config import get_logger

logger = get_logger(__name__)

class EntityMapper(BaseValidator):
    """Maps data between different entity formats."""
    
    def __init__(self, adapter_config: Dict[str, Any]):
        """Initialize entity mapper.
        
        Args:
            adapter_config: Configuration for field adapters
        """
        super().__init__()
        self._adapter_config = adapter_config
        self._mapping_cache: Dict[str, Dict[str, Any]] = {}
        self._file_cache = TextFileCache()
        self._mapped_fields: Set[str] = set()
        self._initialize_adapters()
        
    def _initialize_adapters(self) -> None:
        """Initialize field adapters from configuration."""
        for field_pattern, adapter_config in self._adapter_config.items():
            adapter_type = adapter_config.get('type')
            if not adapter_type:
                logger.warning(f"No adapter type specified for {field_pattern}")
                continue
                
            try:
                adapter = self._create_adapter(adapter_type, adapter_config)
                if adapter:
                    self.register_adapter(field_pattern, adapter)
            except Exception as e:
                logger.error(f"Failed to create adapter for {field_pattern}: {str(e)}")
                
    def _create_adapter(self, adapter_type: str, config: Dict[str, Any]) -> Any:
        """Create field adapter instance.
        
        Args:
            adapter_type: Type of adapter to create
            config: Adapter configuration
            
        Returns:
            Adapter instance
        """
        from .schema_adapters import SchemaAdapterFactory
        try:
            return SchemaAdapterFactory.create_adapter(adapter_type, config)
        except Exception as e:
            logger.error(f"Failed to create {adapter_type} adapter: {str(e)}")
            return None
            
    def map_entity(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Map data to entity format.
        
        Args:
            data: Data to map
            
        Returns:
            Mapped entity data
        """
        result = {}
        self.errors.clear()
        
        try:
            # Apply field mappings
            for field_name, value in data.items():
                if self.validate_field(field_name, value):
                    mapped_value = self._apply_mapping(field_name, value)
                    if mapped_value is not None:
                        result[field_name] = mapped_value
                        self._mapped_fields.add(field_name)
                        
            return result
            
        except Exception as e:
            logger.error(f"Entity mapping failed: {str(e)}")
            raise EntityMappingError(f"Failed to map entity: {str(e)}")
            
    def _validate_field_value(self, field_name: str, value: Any,
                          validation_context: Optional[Dict[str, Any]] = None) -> bool:
        """Validate field value using registered adapter.
        
        Args:
            field_name: Field name to validate
            value: Value to validate
            validation_context: Optional validation context
            
        Returns:
            True if valid, False otherwise
        """
        adapter = self._get_adapter(field_name)
        if not adapter:
            return True  # No adapter means valid
            
        try:
            if not adapter.validate(value, {}, validation_context):
                self.errors.extend(adapter.get_errors())
                return False
            return True
            
        except Exception as e:
            logger.error(f"Validation error for {field_name}: {str(e)}")
            self.errors.append(f"Field validation failed: {str(e)}")
            return False
            
    def _apply_mapping(self, field_name: str, value: Any) -> Any:
        """Apply field mapping transformation.
        
        Args:
            field_name: Name of field to map
            value: Value to transform
            
        Returns:
            Transformed value
        """
        adapter = self._get_adapter(field_name)
        if not adapter:
            return value  # Pass through if no adapter
            
        try:
            return adapter.transform(value)
        except Exception as e:
            logger.error(f"Mapping failed for {field_name}: {str(e)}")
            self.errors.append(f"Field mapping failed: {str(e)}")
            return None
            
    def get_mapping_errors(self) -> List[str]:
        """Get mapping error messages.
        
        Returns:
            List of error messages
        """
        return self.get_validation_errors()
        
    def get_mapping_stats(self) -> Dict[str, Any]:
        """Get mapping statistics.
        
        Returns:
            Dictionary of mapping statistics
        """
        stats = self.get_validation_stats()
        stats.update({
            'mapped_fields': len(self._mapped_fields),
            'adapter_count': len(self._adapters)
        })
        return stats
        
    def clear_caches(self) -> None:
        """Clear all mapping caches."""
        super().clear_cache()
        self._mapping_cache.clear()
        self._file_cache.clear()
        self._mapped_fields.clear()