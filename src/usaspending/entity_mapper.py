"""Entity mapping functionality."""
from typing import Dict, Any, Optional, List, Set
import re
import logging

from .interfaces import IEntityMapper, IValidationMediator, IConfigurationProvider
from .validation_base import BaseValidator
from .exceptions import EntityMappingError
from .component_utils import implements

logger = logging.getLogger(__name__)

@implements(IEntityMapper)
class EntityMapper(BaseValidator, IEntityMapper):
    """Maps data between different entity formats."""

    def __init__(self, 
                 config_provider: IConfigurationProvider,
                 validation_mediator: IValidationMediator):
        """Initialize entity mapper.
        
        Args:
            config_provider: Configuration provider instance
            validation_mediator: Validation mediator instance
        """
        super().__init__()
        self._config_provider = config_provider
        self._validation_mediator = validation_mediator
        self._mapping_cache: Dict[str, Dict[str, Any]] = {}
        self._mapped_fields: Set[str] = set()
        self._error_counts: Dict[str, int] = {}
        self._cache_hits: int = 0
        self._cache_misses: int = 0
        
        # Store entity definitions for quick lookup
        self.entities = self._config_provider.get_config('entities')
        if not self.entities:
            raise ValueError("No entity definitions found in configuration")
            
        self.field_properties = self._config_provider.get_config('field_properties')
        
        # Create ordered list of entities by processing order
        self.entity_order = sorted(
            [(name, cfg.get('entity_processing', {}).get('processing_order', 999))
             for name, cfg in self.entities.items()],
            key=lambda x: x[1]
        )
        
        logger.debug(f"Initialized EntityMapper with {len(self.entities)} entity definitions")

    def map_entity(self, data: Any) -> Dict[str, Any]:
        """Map data to entity format using configuration mappings."""
        result = {}
        self.errors.clear()
        
        try:
            # Convert input to dictionary format
            data_dict = self._ensure_dict_data(data)
            if not data_dict:
                raise ValueError("Input data could not be converted to dictionary format")
            
            # Check cache first
            cache_key = self._generate_cache_key(data_dict)
            if (cache_key in self._mapping_cache):
                self._cache_hits += 1
                return self._mapping_cache[cache_key]
            self._cache_misses += 1
            
            # Determine entity type from entity definitions
            entity_type = self._determine_entity_type(data_dict)
            if not entity_type:
                logger.warning("Could not determine entity type", extra={'fields': list(data_dict.keys())})
                self._increment_error_count('unknown_type')
                return {}
                
            # Get entity configuration
            entity_config = self.entities.get(entity_type, {})
            if not entity_config:
                logger.error(f"Missing configuration for entity type: {entity_type}")
                self._increment_error_count('missing_config')
                return {}
                
            # Add entity type to result
            result['entity_type'] = entity_type
            
            # Validate entity data
            if not self._validation_mediator.validate_entity(entity_type, data_dict):
                self.errors.extend(self._validation_mediator.get_validation_errors())
                self._increment_error_count('validation_failure')
                return {}
            
            # Apply field mappings from entity definition
            field_mappings = entity_config.get('field_mappings', {})
            
            # Special handling for agency entities
            if entity_type == 'agency':
                multi_source = field_mappings.get('multi_source', {})
                agency_key = self._generate_agency_key(data_dict, multi_source)
                if agency_key:
                    result['id'] = agency_key
                    # Apply field mappings
                    agency_fields = self._apply_multi_source_mappings(data_dict, multi_source)
                    result.update(agency_fields)
                else:
                    self._increment_error_count('missing_agency_key')
                    return {}
            else:
                # Apply regular field mappings for other entities
                direct_mappings = field_mappings.get('direct', {})
                result.update(self._apply_direct_mappings(data_dict, direct_mappings))
                
                multi_source = field_mappings.get('multi_source', {})
                result.update(self._apply_multi_source_mappings(data_dict, multi_source))
                
                object_mappings = field_mappings.get('object', {})
                result.update(self._apply_object_mappings(data_dict, object_mappings))
                
                reference_mappings = field_mappings.get('reference', {})
                result.update(self._apply_reference_mappings(data_dict, reference_mappings))

            if self._mapped_fields:
                # Cache successful mapping
                self._mapping_cache[cache_key] = result
                logger.debug(f"Mapped {len(self._mapped_fields)} fields for {entity_type} entity")
                return result
            else:
                logger.warning(f"No fields were mapped for {entity_type} entity")
                self._increment_error_count('no_fields_mapped')
                return {}
            
        except Exception as e:
            logger.error(f"Entity mapping failed: {str(e)}", exc_info=True)
            self._increment_error_count('mapping_error')
            raise EntityMappingError(f"Failed to map entity: {str(e)}")

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

    def _check_key_fields(self, data: Dict[str, Any], entity_type: str) -> bool:
        """Check if data contains required key fields for entity type."""
        entity_config = self.entities.get(entity_type, {})
        key_fields = entity_config.get('key_fields', [])
        field_mappings = entity_config.get('field_mappings', {})
        
        # For agency specifically, check multi-source mappings to ensure we have complete key
        if entity_type == 'agency':
            multi_source = field_mappings.get('multi_source', {})
            agency_key = self._generate_agency_key(data, multi_source)
            return agency_key is not None
        
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

    def _generate_agency_key(self, data: Dict[str, Any], multi_source: Dict[str, Any]) -> Optional[str]:
        """Generate a unique key for an agency entity using composite fields."""
        # Get values for all key components
        agency_code = self._get_field_value_from_sources(data, multi_source.get('agency_code', {}).get('sources', []))
        sub_agency_code = self._get_field_value_from_sources(data, multi_source.get('sub_agency_code', {}).get('sources', []))
        office_code = self._get_field_value_from_sources(data, multi_source.get('office_code', {}).get('sources', []))
        
        # Agency code is required
        if not agency_code:
            return None
            
        # Build composite key with available parts
        key_parts = [agency_code]
        if sub_agency_code:
            key_parts.append(sub_agency_code)
        if office_code:
            key_parts.append(office_code)
            
        return ':'.join(key_parts)

    def _get_field_value_from_sources(self, data: Dict[str, Any], sources: List[str]) -> Optional[Any]:
        """Get first non-empty value from multiple source fields."""
        for source in sources:
            if source in data and data[source]:
                return data[source]
        return None

    def _apply_direct_mappings(self, data: Dict[str, Any], mappings: Dict[str, Any]) -> Dict[str, Any]:
        """Apply direct field mappings."""
        result = {}
        for target_field, mapping in mappings.items():
            if isinstance(mapping, str):
                # Direct string mapping
                if mapping in data:
                    value = data[mapping]
                    if self._validation_mediator.validate_field(mapping, value):
                        result[target_field] = value
                        self._mapped_fields.add(target_field)
            elif isinstance(mapping, dict):
                # Dictionary mapping with 'field' property
                source_field = mapping.get('field')
                if source_field and source_field in data:
                    value = data[source_field]
                    if self._validation_mediator.validate_field(source_field, value):
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
                        if self._validation_mediator.validate_field(sources[0], value):
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
                            value = data[source]
                            if self._validation_mediator.validate_field(source, value):
                                obj_result[obj_field] = value
                    elif isinstance(field_mapping, str) and field_mapping in data:
                        value = data[field_mapping]
                        if self._validation_mediator.validate_field(field_mapping, value):
                            obj_result[obj_field] = value
                if obj_result:
                    result[target_field] = obj_result
                    self._mapped_fields.add(target_field)
        return result

    def _apply_reference_mappings(self, data: Dict[str, Any], mappings: Dict[str, Any]) -> Dict[str, Any]:
        """Apply reference field mappings."""
        result = {}
        for target_field, mapping in mappings.items():
            if isinstance(mapping, dict) and mapping.get('type') == 'entity_reference':
                entity_type = mapping.get('entity')
                
                # Handle key_field directly defined
                if 'key_field' in mapping and mapping['key_field'] in data:
                    key_value = data[mapping['key_field']]
                    if key_value:
                        result[target_field] = {
                            'entity_type': entity_type,
                            'data': {'id': key_value}
                        }
                        logger.debug(f"Created reference {target_field} to {entity_type} with key {key_value}")
                
                # Handle composite keys with key_fields
                elif 'key_fields' in mapping:
                    key_prefix = mapping.get('key_prefix', '')
                    key_values = {}
                    for key_field in mapping['key_fields']:
                        field_name = f"{key_prefix}_{key_field}" if key_prefix else key_field
                        if field_name in data and data[field_name]:
                            key_values[key_field] = data[field_name]
                    
                    if key_values:
                        result[target_field] = {
                            'entity_type': entity_type,
                            'reference_type': mapping.get('reference_type', 'default'),
                            'data': key_values
                        }
        return result

    def _generate_cache_key(self, data: Dict[str, Any]) -> str:
        """Generate cache key for input data."""
        # Sort keys for consistent ordering
        sorted_items = sorted(
            (k, str(v)) for k, v in data.items() 
            if v is not None and v != ""
        )
        return ';'.join(f"{k}={v}" for k, v in sorted_items)

    def _increment_error_count(self, error_type: str) -> None:
        """Increment error counter for given error type."""
        self._error_counts[error_type] = self._error_counts.get(error_type, 0) + 1

    def get_mapping_errors(self) -> List[str]:
        """Get mapping error messages."""
        return self.errors.copy()

    def get_mapping_stats(self) -> Dict[str, Any]:
        """Get mapping statistics."""
        stats = {
            'mapped_fields': len(self._mapped_fields),
            'cache_size': len(self._mapping_cache),
            'error_count': len(self.errors),
            'cache_hits': self._cache_hits,
            'cache_misses': self._cache_misses,
            'error_counts': self._error_counts
        }
        return stats

    def clear_caches(self) -> None:
        """Clear all mapping caches."""
        self._mapping_cache.clear()
        self._mapped_fields.clear()
        super().clear_cache()