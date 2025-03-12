"""Entity factory system."""
from typing import Dict, Any, Optional, List, Type, cast, TypedDict
import logging
from datetime import datetime
from decimal import Decimal

from .core.entity_base import BaseEntityFactory
from .core.interfaces import IConfigurable
from .core.config import ComponentConfig
from .core.types import (
    EntityData, EntityType, EntityConfig,
    FieldType, TransformationRule
)
from .core.exceptions import EntityError
from .core.utils import safe_operation

logger = logging.getLogger(__name__)

class EntityConfigDict(TypedDict):
    fields: Dict[str, Any]
    validations: Dict[str, Any]
    transformations: Dict[str, List[TransformationRule]]
    metadata: Dict[str, Any]

class EntityFactory(BaseEntityFactory, IConfigurable):
    """Creates and manages entity instances."""
    
    def __init__(self) -> None:
        """Initialize entity factory."""
        super().__init__()
        self._entities: Dict[str, EntityConfigDict] = {}
        self._initialized = False
        self._strict_mode = False

    def configure(self, config: ComponentConfig) -> None:
        """Configure factory with settings."""
        if not config or not isinstance(config.settings, dict):
            raise EntityError("Factory configuration is required")
            
        settings = config.settings
        self._strict_mode = settings.get('strict_mode', False)
        
        # Load entity configurations
        entities = settings.get('entities', {})
        for entity_type, entity_config in entities.items():
            self.register_entity(
                EntityType(entity_type),
                cast(Dict[str, Any], entity_config)
            )
            
        self._initialized = True

    @safe_operation
    def register_entity(self, entity_type: EntityType, config: Dict[str, Any]) -> None:
        """Register an entity configuration."""
        if not isinstance(config, dict):
            raise EntityError("Entity configuration must be a dictionary")
            
        entity_config: EntityConfigDict = {
            'fields': config.get('fields', {}),
            'validations': config.get('validations', {}),
            'transformations': config.get('transformations', {}),
            'metadata': config.get('metadata', {})
        }
        
        self._entities[str(entity_type)] = entity_config

    def create_entity(self, entity_type: EntityType, data: Dict[str, Any]) -> Optional[EntityData]:
        """Create an entity instance."""
        if not self._initialized:
            raise EntityError("Factory not initialized")
            
        config = self._entities.get(str(entity_type))
        if not config:
            if self._strict_mode:
                raise EntityError(f"No configuration for entity type: {entity_type}")
            return None

        try:
            # Create base entity with validated/transformed data
            result: EntityData = {
                'type': str(entity_type),
                'data': self._process_entity_data(data, config),
                'metadata': {
                    'created': datetime.utcnow().isoformat(),
                    **config['metadata']
                }
            }
            return result
            
        except Exception as e:
            logger.error(f"Entity creation failed: {str(e)}")
            if self._strict_mode:
                raise
            return None

    def get_entity_types(self) -> List[EntityType]:
        """Get list of registered entity types."""
        return [EntityType(t) for t in self._entities.keys()]

    def get_entity_config(self, entity_type: EntityType) -> Optional[EntityConfig]:
        """Get entity configuration."""
        config_dict = self._entities.get(str(entity_type))
        if config_dict is None:
            return None
        # Convert EntityConfigDict to EntityConfig with correct types
        return EntityConfig(
            name=str(entity_type),
            fields=config_dict['fields'],
            validations=[v for v in config_dict['validations'].values()],  # Convert dict to list
            key_fields=config_dict.get('metadata', {}).get('key_fields', [])  # Get key fields from metadata
        )

    def _process_entity_data(self, data: Dict[str, Any], config: EntityConfigDict) -> Dict[str, Any]:
        """Process entity data using configuration."""
        result = {}
        
        fields = config['fields']
        transformations = config['transformations']
        
        for field_name, field_config in fields.items():
            if field_name in data:
                value = data[field_name]
                
                # Apply field transformations if any
                if field_name in transformations:
                    value = self._apply_transformations(value, transformations[field_name])
                    
                # Store processed value
                result[field_name] = value
                
        return result

    def _apply_transformations(self, value: Any, rules: List[TransformationRule]) -> Any:
        """Apply transformation rules to a value."""
        result = value
        for rule in rules:
            try:
                transformer = self._get_transformer(rule.transform_type)
                if transformer:
                    result = transformer(result, rule.parameters if hasattr(rule, 'parameters') else {})
            except Exception as e:
                logger.error(f"Transformation failed: {str(e)}")
                if self._strict_mode:
                    raise
        return result

    def _get_transformer(self, transform_type: str) -> Optional[Any]:
        """Get transformer function by type."""
        transformers = {
            'uppercase': str.upper,
            'lowercase': str.lower,
            'strip': str.strip,
            'decimal': Decimal,
            'integer': int,
            'boolean': bool
        }
        return transformers.get(transform_type)

    def cleanup(self) -> None:
        """Clean up resources."""
        self._entities.clear()
        self._initialized = False

__all__ = ['EntityFactory']