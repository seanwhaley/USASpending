"""Schema mapping system for converting field_properties to schema adapters."""
from typing import Dict, Any, Set, List, Optional
from .schema_adapters import SchemaAdapterFactory, FieldAdapter
from .config_schema import FieldProperties, TransformOperation

class SchemaMapping:
    """Maps field properties configuration to schema adapters."""
    
    # Default type mappings from field_properties to adapter types
    TYPE_MAPPINGS = {
        'date': {
            'standard': 'date',
            'not_future': 'date',
            'comparison': 'date'
        },
        'numeric': {
            'money': 'decimal',
            'integer': 'integer',
            'decimal': 'decimal',
            'comparison': 'decimal'
        },
        'string': {
            'agency_code': 'string',
            'uei': 'string',
            'naics': 'string',
            'psc': 'string',
            'zip_code': 'string',
            'phone': 'string',
            'max_length': 'string',
            'state_code': 'string',
            'country_code': 'string'
        },
        'enum': {
            'contract_type': 'enum',
            'idv_type': 'enum',
            'action_type': 'enum',
            'contract_pricing': 'enum',
            'governmental_functions': 'enum',
            'yes_no_extended': 'enum'
        },
        'boolean': {
            'standard': 'boolean'
        }
    }

    # Standard transformation pipelines for field types
    STANDARD_TRANSFORMS = {
        'money': [
            TransformOperation(type='strip_characters', characters='$,'),
            TransformOperation(type='convert_to_decimal'),
            TransformOperation(type='round_number', places=2)
        ],
        'zip_code': [
            TransformOperation(type='strip_characters', characters=' -'),
            TransformOperation(type='pad_left', length=5, character='0'),
            TransformOperation(type='truncate', max_length=5)
        ],
        'phone': [
            TransformOperation(type='strip_characters', characters='()- '),
            TransformOperation(type='extract_pattern', pattern=r'\d{10}')
        ],
        'agency_code': [
            TransformOperation(type='strip_characters', characters=' '),
            TransformOperation(type='uppercase')
        ],
        'uei': [
            TransformOperation(type='strip_characters', characters=' -'),
            TransformOperation(type='uppercase')
        ],
        'naics': [
            TransformOperation(type='strip_characters', characters=' -'),
            TransformOperation(type='pad_left', length=6, character='0')
        ],
        'psc': [
            TransformOperation(type='strip_characters', characters=' '),
            TransformOperation(type='uppercase')
        ]
    }

    def __init__(self, field_properties: Dict[str, Any]):
        """Initialize schema mapping with field properties configuration."""
        self.field_properties = field_properties
        self._adapter_cache: Dict[str, FieldAdapter] = {}
    
    def get_adapter_for_field(self, field_name: str) -> Optional[FieldAdapter]:
        """Get the appropriate schema adapter for a field."""
        # Check cache first
        if field_name in self._adapter_cache:
            return self._adapter_cache[field_name]
            
        # Find field type and configuration
        field_type, field_config = self._find_field_config(field_name)
        if not field_type or not field_config:
            return None
            
        # Convert field configuration to adapter config
        adapter_type = self._map_to_adapter_type(field_type, field_config)
        if not adapter_type:
            return None
            
        adapter_config = self._create_adapter_config(field_type, field_config)
        
        # Create and cache adapter
        try:
            adapter = SchemaAdapterFactory.create(adapter_type, adapter_config)
            if adapter:
                self._adapter_cache[field_name] = adapter
            return adapter
        except ValueError as e:
            return None
    
    def _find_field_config(self, field_name: str) -> tuple[Optional[str], Optional[Dict[str, Any]]]:
        """Find the field type and configuration for a field name."""
        for type_name, type_config in self.field_properties.items():
            for subtype, subtype_config in type_config.items():
                if 'fields' in subtype_config:
                    if field_name in subtype_config['fields']:
                        return type_name, subtype_config
                    # Check for pattern matches
                    for pattern in subtype_config['fields']:
                        if '*' in pattern:
                            import fnmatch
                            if fnmatch.fnmatch(field_name, pattern):
                                return type_name, subtype_config
        return None, None
    
    def _map_to_adapter_type(self, field_type: str, field_config: Dict[str, Any]) -> Optional[str]:
        """Map field type to adapter type."""
        type_mappings = self.TYPE_MAPPINGS.get(field_type, {})
        for subtype, adapter_type in type_mappings.items():
            if subtype in field_config:
                return adapter_type
        return None
    
    def _create_adapter_config(self, field_type: str, field_config: Dict[str, Any]) -> Dict[str, Any]:
        """Create adapter configuration from field configuration."""
        adapter_config = {}
        
        # Map validation rules
        if 'validation' in field_config:
            validation = field_config['validation']
            
            # Handle format/pattern
            if 'format' in validation:
                adapter_config['format'] = validation['format']
            if 'pattern' in validation:
                adapter_config['pattern'] = validation['pattern']
                
            # Handle numeric constraints
            if 'precision' in validation:
                adapter_config['precision'] = validation['precision']
            if 'min_value' in validation:
                adapter_config['min_value'] = validation['min_value']
            if 'max_value' in validation:
                adapter_config['max_value'] = validation['max_value']
                
            # Handle enum values
            if 'values' in validation:
                adapter_config['values'] = validation['values']
                
            # Handle error messages
            if 'error_message' in validation:
                adapter_config['error_message'] = validation['error_message']
        
        # Map transformation rules if present
        if 'transformation' in field_config:
            transform = field_config['transformation']
            
            # Handle timing
            if 'timing' in transform:
                adapter_config['transform_timing'] = transform['timing']
                
            # Handle operations
            if 'operations' in transform:
                adapter_config['operations'] = transform['operations']
        
        return adapter_config
    
    def clear_cache(self) -> None:
        """Clear the adapter cache."""
        self._adapter_cache.clear()

    @classmethod
    def create_adapter_config(cls, field_props: FieldProperties) -> Dict[str, Any]:
        """Create adapter configuration from field properties."""
        adapter_config: Dict[str, Any] = {}
        
        # Map validation rules
        if field_props.validation:
            validation = field_props.validation
            
            if validation.format:
                adapter_config['format'] = validation.format
            if validation.pattern:
                adapter_config['pattern'] = validation.pattern
            if validation.min_value is not None:
                adapter_config['min_value'] = validation.min_value
            if validation.max_value is not None:
                adapter_config['max_value'] = validation.max_value
            if validation.precision is not None:
                adapter_config['precision'] = validation.precision
            if validation.values:
                adapter_config['values'] = validation.values
            if validation.error_message:
                adapter_config['error_message'] = validation.error_message
        
        # Map transformation rules
        if field_props.transformation:
            transform = field_props.transformation
            adapter_config['transformation'] = {
                'timing': transform.timing,
                'operations': []
            }
            
            # Add standard transforms for field type if available
            field_type = field_props.type
            if field_type in cls.STANDARD_TRANSFORMS:
                adapter_config['transformation']['operations'].extend(
                    cls.STANDARD_TRANSFORMS[field_type]
                )
            
            # Add custom transforms
            adapter_config['transformation']['operations'].extend(transform.operations)
        
        return adapter_config

    @classmethod
    def get_adapter_type(cls, field_type: str, subtype: Optional[str] = None) -> str:
        """Get the appropriate adapter type for a field type."""
        type_map = cls.TYPE_MAPPINGS.get(field_type, {})
        if subtype and subtype in type_map:
            return type_map[subtype]
        return type_map.get('standard', field_type)

    @classmethod
    def get_standard_transforms(cls, field_type: str) -> List[TransformOperation]:
        """Get standard transformations for a field type."""
        return cls.STANDARD_TRANSFORMS.get(field_type, [])