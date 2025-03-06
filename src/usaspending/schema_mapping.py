"""Schema mapping system for converting field_properties to schema adapters."""
from typing import Dict, Any, List, Optional, Type
from abc import ABC, abstractmethod

from .interfaces import ISchemaAdapter, ITransformerFactory
from .config_schema import FieldProperties, TransformOperation
from .schema_adapters import SchemaAdapterFactory  # Fixed import name
from .logging_config import get_logger

logger = get_logger(__name__)

class SchemaMapping:
    """Maps field properties configuration to schema adapters."""
    
    def __init__(self, transformer_factory: ITransformerFactory):
        """Initialize schema mapping with transformer factory."""
        self.transformer_factory = transformer_factory
        
    # Type mappings define standard adapter types for field types
    TYPE_MAPPINGS = {
        'numeric': {
            'money': 'decimal',
            'decimal': 'decimal',
            'integer': 'integer',
            'standard': 'decimal'
        },
        'date': {
            'standard': 'date'
        },
        'boolean': {
            'standard': 'boolean'
        }
    }

    # Standard transformation pipelines for field types
    STANDARD_TRANSFORMS = {
        'money': [
            TransformOperation(type='strip_characters', characters='$,.'),
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
        ]
    }

    def create_adapter(self, field_type: str, field_properties: Dict[str, Any]) -> Optional[ISchemaAdapter]:
        """Create an adapter instance for a field type with properties."""
        try:
            # Get appropriate adapter type
            adapter_type = self.get_adapter_type(
                field_type,
                field_properties.get('subtype')
            )

            # Create base configuration
            config = {
                'type': adapter_type,
                'field_type': field_type,
                **field_properties
            }

            # Get standard transformations for the field type
            standard_transforms = self.get_standard_transforms(field_type)
            if standard_transforms:
                config['transforms'] = standard_transforms

            # Create the adapter using SchemaAdapterFactory directly
            adapter = SchemaAdapterFactory().create_adapter(adapter_type, **config)
            if not adapter:
                logger.error(f"Failed to create adapter for type {field_type}")
                return None

            # Add transformers from field properties if specified
            if 'transformation' in field_properties:
                self._add_transformers(adapter, field_properties['transformation'])

            return adapter

        except Exception as e:
            logger.error(f"Error creating adapter for {field_type}: {e}")
            return None

    def _add_transformers(self, adapter: ISchemaAdapter, transform_config: Dict[str, Any]) -> None:
        """Add transformers to an adapter based on configuration."""
        try:
            # Handle single transform
            if 'type' in transform_config:
                transformer = self.transformer_factory.create(
                    transform_config['type'],
                    transform_config.get('config', {})
                )
                if transformer:
                    adapter.add_transformer(transformer)

            # Handle operation list
            elif 'operations' in transform_config:
                for op in transform_config['operations']:
                    if 'type' not in op:
                        continue
                    transformer = self.transformer_factory.create(
                        op['type'],
                        op.get('config', {})
                    )
                    if transformer:
                        adapter.add_transformer(transformer)

        except Exception as e:
            logger.error(f"Error adding transformers: {e}")

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