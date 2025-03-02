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
    
    def __init__(self, config: Dict[str, Any], entity_type: str):
        """
        Initialize entity mapper.
        
        Args:
            config: Configuration dictionary or instance
            entity_type: Type of entity to map
        """
        self.entity_type = entity_type
        self.config = config
        self.field_mapping = self._get_field_mapping()
    
    def _get_field_mapping(self) -> Dict:
        """Get field mapping for the entity type from config."""
        entities_config = self.config.get("entities", {})
        entity_config = entities_config.get(self.entity_type, {})
        
        if not entity_config or "field_mappings" not in entity_config:
            raise EntityMappingError(f"No field mapping found for entity type: {self.entity_type}")
        return entity_config["field_mappings"]
    
    def extract_entity_data(self, source_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract entity data from source data based on mappings."""
        # Check for required key fields
        entity_config = self.config.get("entities", {}).get(self.entity_type, {})
        key_fields = entity_config.get("key_fields", [])
        
        # Skip records missing required key fields
        for key_field in key_fields:
            if key_field not in source_data or not source_data[key_field]:
                return None
        
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
        for target_field, mapping in self.field_mapping["direct"].items():
            source_field_name = mapping.get("field") if isinstance(mapping, dict) else mapping
            
            if source_field_name in source_data:
                value = source_data[source_field_name]
                
                # Apply transformation if configured
                if isinstance(mapping, dict) and "transformation" in mapping:
                    try:
                        # Create a type converter and apply the transformation
                        converter = TypeConverter(self.config)
                        transform_type = mapping["transformation"].get("type")
                        if transform_type:
                            value = converter.convert_value(value, transform_type)
                            if value is None:
                                # Skip if transformation failed
                                continue
                    except Exception as e:
                        logger.warning(f"Transformation error for {target_field}: {str(e)}")
                        continue
                        
                result[target_field] = value
    
    def _map_multi_source_fields(self, source_data: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Map fields that combine multiple source fields."""
        for target_field, mapping_config in self.field_mapping["multi_source"].items():
            if "fields" not in mapping_config:
                logger.warning(f"Invalid multi_source mapping for {target_field}")
                continue
                
            source_values = []
            for field in mapping_config["fields"]:
                if field in source_data:
                    source_values.append(source_data[field])
            
            if source_values:
                if mapping_config.get("combine_function") == "concatenate":
                    separator = " "  # Default separator
                    result[target_field] = separator.join(str(v) for v in source_values if v is not None)
    
    def _map_object_fields(self, source_data: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Map nested object fields."""
        for target_field, mapping_config in self.field_mapping["object"].items():
            if "fields" not in mapping_config:
                continue
                
            nested_result = {}
            for prop_name, prop_mapping in mapping_config["fields"].items():
                source_field = prop_mapping.get("field") if isinstance(prop_mapping, dict) else prop_mapping
                
                if source_field and source_field in source_data:
                    value = source_data[source_field]
                    
                    # Apply transformation if configured
                    if isinstance(prop_mapping, dict) and "transformation" in prop_mapping:
                        try:
                            converter = TypeConverter(self.config)
                            transform_type = prop_mapping["transformation"].get("type")
                            if transform_type:
                                value = converter.convert_value(value, transform_type)
                                if value is None:
                                    # Skip if transformation or validation failed
                                    continue
                        except Exception as e:
                            logger.warning(f"Transformation error for {prop_name}: {str(e)}")
                            continue
                    
                    nested_result[prop_name] = value
            
            if nested_result:
                result[target_field] = nested_result
    
    def _map_reference_fields(self, source_data: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Map fields that reference other entities."""
        for target_field, mapping_config in self.field_mapping["reference"].items():
            if "entity_type" not in mapping_config or "fields" not in mapping_config:
                continue
                
            ref_data = {}
            for field_name, field_mapping in mapping_config["fields"].items():
                source_field = field_mapping.get("field") if isinstance(field_mapping, dict) else field_mapping
                
                if source_field and source_field in source_data:
                    ref_data[field_name] = source_data[source_field]
            
            if ref_data:
                result[target_field] = {
                    "type": mapping_config["entity_type"],
                    "data": ref_data
                }
    
    def _map_template_fields(self, source_data: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Map fields using template strings."""
        for target_field, mapping_config in self.field_mapping["template"].items():
            if "template" not in mapping_config or "fields" not in mapping_config:
                continue
                
            template = mapping_config["template"]
            # Create a dictionary of field values for template formatting
            template_values = {}
            for key, source_field in mapping_config["fields"].items():
                if source_field in source_data:
                    template_values[key] = source_data[source_field]
                else:
                    template_values[key] = ""
                    
            # Apply template
            try:
                result[target_field] = template.format(**template_values)
            except (KeyError, ValueError) as e:
                logger.warning(f"Template formatting error for {target_field}: {str(e)}")