"""Entity data mapping and conversion functionality."""
from typing import Dict, Any, Optional, List, Set, Union, Callable
from datetime import datetime
import re
import logging
from .config import ConfigManager
from .utils import TypeConverter, generate_entity_key
from .exceptions import EntityMappingError

logger = logging.getLogger(__name__)

class EntityMapper:
    """Maps source data to entity fields based on configuration."""
    
    def __init__(self, entity_type: str):
        self.entity_type = entity_type
        self.config = ConfigManager().get_instance()
        self.field_mapping = self._get_field_mapping()
    
    def _get_field_mapping(self) -> Dict:
        """Get field mapping for the entity type from config."""
        entity_config = self.config.get_entity_config(self.entity_type)
        if not entity_config or "field_mapping" not in entity_config:
            raise EntityMappingError(f"No field mapping found for entity type: {self.entity_type}")
        return entity_config["field_mapping"]
    
    def map_data(self, source_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map source data to entity fields."""
        result = {}
        
        # Process different mapping categories
        if "direct" in self.field_mapping:
            self._map_direct_fields(source_data, result)
        
        if "multi_source" in self.field_mapping:
            self._map_multi_source_fields(source_data, result)
        
        if "object" in self.field_mapping:
            self._map_object_fields(source_data, result)
        
        if "reference" in self.field_mapping:
            self._map_reference_fields(source_data, result)
        
        if "template" in self.field_mapping:
            self._map_template_fields(source_data, result)
        
        return result
    
    def _map_direct_fields(self, source_data: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Map fields with direct 1:1 mapping."""
        for target_field, source_field in self.field_mapping["direct"].items():
            if isinstance(source_field, str):
                if source_field in source_data:
                    result[target_field] = source_data[source_field]
            elif isinstance(source_field, dict) and "field" in source_field:
                source_field_name = source_field["field"]
                if source_field_name in source_data:
                    result[target_field] = source_data[source_field_name]
    
    def _map_multi_source_fields(self, source_data: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Map fields that combine multiple source fields."""
        for target_field, mapping_config in self.field_mapping["multi_source"].items():
            if "fields" not in mapping_config:
                logger.warning(f"Invalid multi_source mapping for {target_field}")
                continue
                
            source_values = {}
            for field in mapping_config["fields"]:
                if field in source_data:
                    source_values[field] = source_data[field]
            
            if "method" in mapping_config:
                # Apply the specified combination method
                method = mapping_config["method"]
                if method == "concat":
                    separator = mapping_config.get("separator", "")
                    result[target_field] = separator.join(str(v) for v in source_values.values() if v is not None)
                elif method == "first_non_empty":
                    for field, value in source_values.items():
                        if value:
                            result[target_field] = value
                            break
                # Add other methods as needed
    
    def _map_object_fields(self, source_data: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Map nested object fields."""
        for target_field, mapping_config in self.field_mapping["object"].items():
            if "properties" not in mapping_config:
                continue
                
            nested_result = {}
            for prop_name, prop_mapping in mapping_config["properties"].items():
                source_field = prop_mapping.get("source_field")
                if source_field and source_field in source_data:
                    nested_result[prop_name] = source_data[source_field]
            
            if nested_result:
                result[target_field] = nested_result
    
    def _map_reference_fields(self, source_data: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Map fields that reference other entities."""
        for target_field, mapping_config in self.field_mapping["reference"].items():
            if "entity" not in mapping_config or "key_field" not in mapping_config:
                continue
                
            key_field = mapping_config["key_field"]
            if key_field in source_data:
                result[target_field] = {
                    "entity_type": mapping_config["entity"],
                    "key": source_data[key_field]
                }
    
    def _map_template_fields(self, source_data: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Map fields using template strings."""
        for target_field, mapping_config in self.field_mapping["template"].items():
            if "template" not in mapping_config:
                continue
                
            template = mapping_config["template"]
            # Simple template substitution
            try:
                # Create a copy of source_data to use for formatting
                format_data = {k: (v if v is not None else "") for k, v in source_data.items()}
                result[target_field] = template.format(**format_data)
            except (KeyError, ValueError) as e:
                logger.warning(f"Template formatting error for {target_field}: {str(e)}")