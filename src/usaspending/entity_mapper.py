"""Entity mapping functionality for transforming data."""
from typing import Dict, Any, Optional, List, Set, Union
from dataclasses import dataclass
import re
from csv import DictReader

from . import get_logger, ConfigurationError
from .validation_base import BaseValidator
from .text_file_cache import TextFileCache
from .exceptions import EntityMappingError
from .interfaces import IEntityMapper

logger = get_logger(__name__)

class EntityMapper(BaseValidator):
    """Maps data between different entity formats."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize entity mapper with configuration."""
        super().__init__()
        self._config = config
        self._mapping_cache: Dict[str, Dict[str, Any]] = {}
        self._file_cache = TextFileCache()
        self._mapped_fields: Set[str] = set()
        
        # Store entity definitions for quick lookup
        self.entities = self._config.get('entities', {})
        self.field_properties = self._config.get('field_properties', {})
        
        # Create ordered list of entities by processing order
        self.entity_order = sorted(
            [(name, cfg.get('entity_processing', {}).get('processing_order', 999))
             for name, cfg in self.entities.items()],
            key=lambda x: x[1]
        )
        
        logger.debug(f"Initialized EntityMapper with {len(self.entities)} entity definitions")
        
    def _ensure_dict_data(self, data: Any) -> Dict[str, Any]:
        """Ensure data is in dictionary format."""
        if isinstance(data, dict):
            return data
        elif hasattr(data, '_asdict'):  # Handle namedtuple-like objects
            return data._asdict()
        elif hasattr(data, 'items'):  # Handle dict-like objects
            return dict(data.items())
        elif isinstance(data, (list, tuple)) and len(data) >= 2:
            return dict(data)
        else:
            logger.warning(f"Could not convert data to dictionary: {type(data)}")
            return {}

    def _get_field_value_from_sources(self, data: Dict[str, Any], sources: List[str]) -> Optional[Any]:
        """Get first non-empty value from multiple source fields."""
        for source in sources:
            if source in data and data[source]:
                return data[source]
        return None

    def _check_key_fields(self, data: Dict[str, Any], entity_type: str) -> bool:
        """Check if data contains required key fields for entity type."""
        entity_config = self.entities.get(entity_type, {})
        key_fields = entity_config.get('key_fields', [])
        field_mappings = entity_config.get('field_mappings', {})
        
        # For agency specifically, check multi-source mappings
        if entity_type == 'agency':
            multi_source = field_mappings.get('multi_source', {})
            # Need at least agency_code to identify an agency
            agency_sources = multi_source.get('agency_code', {}).get('sources', [])
            if agency_sources and any(source in data and data[source] for source in agency_sources):
                logger.debug(f"Found agency key in sources: {agency_sources}")
                return True
            return False
            
        # For other entities, check direct and multi-source mappings for key fields
        for key_field in key_fields:
            # Check direct mappings first
            direct_mappings = field_mappings.get('direct', {})
            if key_field in direct_mappings:
                mapping = direct_mappings[key_field]
                if isinstance(mapping, str) and mapping in data:
                    return True
                elif isinstance(mapping, dict):
                    source_field = mapping.get('field')
                    if source_field and source_field in data:
                        return True
                        
            # Then check multi-source mappings
            multi_source = field_mappings.get('multi_source', {})
            if key_field in multi_source:
                sources = multi_source[key_field].get('sources', [])
                if any(source in data and data[source] for source in sources):
                    return True
                    
        return False

    def _determine_entity_type(self, data: Dict[str, Any]) -> Optional[str]:
        """Determine entity type from data based on entity definitions."""
        field_values = self._ensure_dict_data(data)
        
        # Check entities in processing order
        for entity_type, order in self.entity_order:
            if self._check_key_fields(field_values, entity_type):
                logger.debug(f"Determined entity type: {entity_type} with processing order {order}")
                return entity_type
                
        logger.debug(f"Could not determine entity type from fields: {list(field_values.keys())}")
        return None

    def _apply_direct_mappings(self, data: Dict[str, Any], mappings: Dict[str, Any]) -> Dict[str, Any]:
        """Apply direct field mappings."""
        result = {}
        for target_field, mapping in mappings.items():
            if isinstance(mapping, str):
                # Direct string mapping
                if mapping in data:
                    value = data[mapping]
                    if self.validate_field(mapping, value):
                        result[target_field] = value
                        self._mapped_fields.add(target_field)
            elif isinstance(mapping, dict):
                # Dictionary mapping with 'field' property
                source_field = mapping.get('field')
                if source_field and source_field in data:
                    value = data[source_field]
                    if self.validate_field(source_field, value):
                        result[target_field] = value
                        self._mapped_fields.add(target_field)
        return result

    def _apply_multi_source_mappings(self, data: Dict[str, Any], mappings: Dict[str, Any]) -> Dict[str, Any]:
        """Apply multi-source field mappings."""
        result = {}
        for target_field, mapping in mappings.items():
            if isinstance(mapping, dict):
                sources = mapping.get('sources', [])
                strategy = mapping.get('strategy', 'first_non_empty')
                
                if strategy == 'first_non_empty':
                    value = self._get_field_value_from_sources(data, sources)
                    if value is not None:
                        if self.validate_field(sources[0], value):  # Validate using first source field
                            result[target_field] = value
                            self._mapped_fields.add(target_field)
                            logger.debug(f"Mapped {target_field} from multi-source: {value}")
        return result

    def _apply_object_mappings(self, data: Dict[str, Any], mappings: Dict[str, Any]) -> Dict[str, Any]:
        """Apply object field mappings."""
        result = {}
        for target_field, mapping in mappings.items():
            if isinstance(mapping, dict) and mapping.get('type') == 'object':
                fields = mapping.get('fields', {})
                obj_result = {}
                for obj_field, field_mapping in fields.items():
                    if isinstance(field_mapping, dict):
                        source = field_mapping.get('field')
                        if source and source in data:
                            obj_result[obj_field] = data[source]
                    elif isinstance(field_mapping, str) and field_mapping in data:
                        obj_result[obj_field] = data[field_mapping]
                if obj_result:
                    result[target_field] = obj_result
        return result
        
    def map_entity(self, data: Any) -> Dict[str, Any]:
        """Map data to entity format using configuration mappings."""
        result = {}
        self.errors.clear()
        
        try:
            # Convert input to dictionary format
            data_dict = self._ensure_dict_data(data)
            
            # Determine entity type from entity definitions
            entity_type = self._determine_entity_type(data_dict)
            if not entity_type:
                return {}
                
            # Get entity configuration
            entity_config = self.entities.get(entity_type, {})
            if not entity_config:
                logger.error(f"Missing configuration for entity type: {entity_type}")
                return {}
                
            # Add entity type to result
            result['entity_type'] = entity_type
            
            # Apply field mappings from entity definition
            field_mappings = entity_config.get('field_mappings', {})
            
            # Apply multi-source mappings first for agency
            if entity_type == 'agency':
                multi_source = field_mappings.get('multi_source', {})
                agency_fields = self._apply_multi_source_mappings(data_dict, multi_source)
                result.update(agency_fields)
                logger.debug(f"Mapped agency fields: {list(agency_fields.keys())}")
            
            # Apply direct mappings
            direct_mappings = field_mappings.get('direct', {})
            result.update(self._apply_direct_mappings(data_dict, direct_mappings))
            
            # Apply multi-source mappings for non-agency entities
            if entity_type != 'agency':
                multi_source = field_mappings.get('multi_source', {})
                result.update(self._apply_multi_source_mappings(data_dict, multi_source))
            
            # Apply object mappings
            object_mappings = field_mappings.get('object', {})
            result.update(self._apply_object_mappings(data_dict, object_mappings))
            
            # Log mapping results
            logger.debug(f"Mapped {len(self._mapped_fields)} fields for {entity_type} entity")
            
            return result
            
        except Exception as e:
            logger.error(f"Entity mapping failed: {str(e)}", exc_info=True)
            raise EntityMappingError(f"Failed to map entity: {str(e)}")

    def _validate_field_value(self, field_name: str, value: Any,
                          validation_context: Optional[Dict[str, Any]] = None) -> bool:
        """Validate field value using field properties from config."""
        try:
            # Find matching field property type
            for type_name, type_config in self.field_properties.items():
                fields = type_config.get('fields', [])
                
                # Check exact match
                if field_name in fields:
                    validation = type_config.get('validation', {})
                    return self._apply_validation_rules(value, validation, validation_context)
                    
                # Check pattern match
                for field_pattern in fields:
                    if '*' in field_pattern:
                        pattern = field_pattern.replace('*', '.*')
                        if re.match(pattern, field_name):
                            validation = type_config.get('validation', {})
                            return self._apply_validation_rules(value, validation, validation_context)
            
            return True  # No validation rules found
            
        except Exception as e:
            logger.error(f"Validation error for {field_name}: {str(e)}")
            self.errors.append(f"Field validation failed: {str(e)}")
            return False
            
    def _apply_validation_rules(self, value: Any, validation: Dict[str, Any],
                             context: Optional[Dict[str, Any]] = None) -> bool:
        """Apply validation rules from configuration."""
        # Get validation type and rules
        validation_type = validation.get('type')
        if not validation_type:
            return True
            
        try:
            if validation_type == 'string':
                if not isinstance(value, str):
                    return False
                pattern = validation.get('pattern')
                if pattern and not re.match(pattern, value):
                    return False
                max_length = validation.get('max_length')
                if max_length and len(value) > max_length:
                    return False
                    
            elif validation_type == 'integer':
                try:
                    int_value = int(value)
                    min_value = validation.get('min_value')
                    max_value = validation.get('max_value')
                    if min_value is not None and int_value < min_value:
                        return False
                    if max_value is not None and int_value > max_value:
                        return False
                except (ValueError, TypeError):
                    return False
                    
            elif validation_type == 'decimal':
                try:
                    float_value = float(value)
                    min_value = validation.get('min_value')
                    max_value = validation.get('max_value')
                    if min_value is not None and float_value < min_value:
                        return False
                    if max_value is not None and float_value > max_value:
                        return False
                except (ValueError, TypeError):
                    return False
                    
            elif validation_type == 'enum':
                allowed_values = validation.get('values', {})
                return str(value).upper() in (v.upper() for v in allowed_values)
                
            elif validation_type == 'boolean':
                true_values = validation.get('true_values', [])
                false_values = validation.get('false_values', [])
                str_value = str(value).lower()
                return str_value in (v.lower() for v in true_values + false_values)
                
            return True
            
        except Exception as e:
            logger.error(f"Error applying validation rules: {str(e)}")
            return False
            
    def get_mapping_errors(self) -> List[str]:
        """Get mapping error messages."""
        return self.get_validation_errors()
        
    def get_mapping_stats(self) -> Dict[str, Any]:
        """Get mapping statistics."""
        stats = self.get_validation_stats()
        stats.update({
            'mapped_fields': len(self._mapped_fields)
        })
        return stats
        
    def clear_caches(self) -> None:
        """Clear all mapping caches."""
        super().clear_cache()
        self._mapping_cache.clear()
        self._file_cache.clear()
        self._mapped_fields.clear()