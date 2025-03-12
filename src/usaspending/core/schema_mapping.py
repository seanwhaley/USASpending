"""Schema mapping system for converting field_properties to schema adapters."""
from typing import Dict, Any, List, Optional, Type, cast, Literal, Protocol
from abc import ABC, abstractmethod

from .types import FieldType, TransformationRule, TransformerType
from .adapters import AdapterFactory, BaseAdapter
from .transformers import TransformerFactory, TransformationEngine, BaseTransformer
from .logging_config import get_logger

logger = get_logger(__name__)

class TransformableAdapter(Protocol):
    """Protocol for adapters that support transformations."""
    transformers: List[BaseTransformer]

class SchemaMapping:
    """Maps field properties configuration to schema adapters."""
    
    def __init__(self, transformer_factory: TransformerFactory) -> None:
        """Initialize schema mapping with transformer factory."""
        self.transformer_factory = transformer_factory
        
    # Type mappings define standard adapter types for field types
    TYPE_MAPPINGS: Dict[str, Dict[str, TransformerType]] = {
        'numeric': {
            'money': 'numeric',
            'decimal': 'numeric',
            'integer': 'numeric',
            'standard': 'numeric'
        },
        'date': {
            'standard': 'date'
        },
        'boolean': {
            'standard': 'boolean'
        },
        'string': {
            'standard': 'string'
        },
        'enum': {
            'standard': 'enum'
        }
    }

    # Standard transformation rules for field types
    STANDARD_TRANSFORMS: Dict[str, List[TransformationRule]] = {
        'money': [
            TransformationRule(
                field_name="",  # Will be set during creation
                transform_type='string',
                parameters={"strip_chars": "$,."}
            ),
            TransformationRule(
                field_name="",
                transform_type='numeric',
                parameters={"decimal": True}
            ),
            TransformationRule(
                field_name="",
                transform_type='numeric',
                parameters={"round": 2}
            )
        ],
        'zip_code': [
            TransformationRule(
                field_name="",
                transform_type='string',
                parameters={"strip_chars": " -" }
            ),
            TransformationRule(
                field_name="",
                transform_type='string',
                parameters={"pad": {"side": "left", "length": 5, "char": "0"}}
            ),
            TransformationRule(
                field_name="",
                transform_type='string',
                parameters={"max_length": 5}
            )
        ],
        'phone': [
            TransformationRule(
                field_name="",
                transform_type='string',
                parameters={"strip_chars": "()- "}
            ),
            TransformationRule(
                field_name="",
                transform_type='string',
                parameters={"pattern": r'\d{10}'}
            )
        ],
        'agency_code': [
            TransformationRule(
                field_name="",
                transform_type='string',
                parameters={"strip_chars": " "}
            ),
            TransformationRule(
                field_name="",
                transform_type='string',
                parameters={"case": "upper"}
            )
        ],
        'uei': [
            TransformationRule(
                field_name="",
                transform_type='string',
                parameters={"strip_chars": " -" }
            ),
            TransformationRule(
                field_name="",
                transform_type='string',
                parameters={"case": "upper"}
            )
        ]
    }

    def create_adapter(self, field_type: str, field_properties: Dict[str, Any]) -> Optional[BaseAdapter[Any]]:
        """Create an adapter instance for a field type with properties."""
        try:
            # Get appropriate adapter type and ensure it's a valid TransformerType
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

            # Create transformations list from field properties
            transformations: List[Dict[str, Any]] = []
            
            # Add standard transformations for the field type if any
            std_transforms = self.get_standard_transforms(field_type)
            for transform in std_transforms:
                transformations.append({
                    "type": transform.transform_type,
                    "parameters": transform.parameters
                })

            # Add custom transformations from field properties
            if 'transformation' in field_properties:
                transform_config = field_properties['transformation']
                if isinstance(transform_config, dict):
                    if 'type' in transform_config:
                        transformations.append(transform_config)
                    elif 'operations' in transform_config:
                        transformations.extend(transform_config['operations'])

            # Create the adapter using AdapterFactory
            field_type_enum = self._get_field_type(field_type)
            adapter = AdapterFactory.create_adapter(
                field_type_enum,
                transformations=transformations
            )
            
            if not adapter:
                logger.error(f"Failed to create adapter for type {field_type}")
                return None

            return adapter

        except Exception as e:
            logger.error(f"Error creating adapter for {field_type}: {e}")
            return None

    def _create_transformer(self, transform_config: Dict[str, Any]) -> Optional[BaseTransformer]:
        """Create a transformer from configuration."""
        try:
            transformer_type = cast(TransformerType, transform_config['type'])
            return self.transformer_factory.create_transformer(
                transformer_type,
                parameters=transform_config.get('parameters', {})
            )
        except Exception as e:
            logger.error(f"Error creating transformer: {e}")
            return None

    @classmethod
    def get_adapter_type(cls, field_type: str, subtype: Optional[str] = None) -> TransformerType:
        """Get the appropriate adapter type for a field type."""
        type_map = cls.TYPE_MAPPINGS.get(field_type, {})
        if subtype and subtype in type_map:
            return type_map[subtype]
        return type_map.get('standard', 'string')

    @classmethod
    def get_standard_transforms(cls, field_type: str) -> List[TransformationRule]:
        """Get standard transformations for a field type."""
        return cls.STANDARD_TRANSFORMS.get(field_type, [])

    @staticmethod
    def _get_field_type(field_type: str) -> FieldType:
        """Convert string field type to FieldType enum."""
        try:
            return FieldType[field_type.upper()]
        except KeyError:
            logger.warning(f"Unknown field type {field_type}, defaulting to STRING")
            return FieldType.STRING