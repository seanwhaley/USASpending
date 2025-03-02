"""Validation system using schema adapters."""
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, field
from collections import defaultdict
import logging

from .schema_adapters import SchemaAdapterFactory, FieldAdapter
from .schema_mapping import SchemaMapping

logger = logging.getLogger(__name__)

@dataclass
class ValidationResult:
    """Result of a field validation."""
    valid: bool
    field_name: str
    error_message: Optional[str] = None
    error_type: Optional[str] = None
    transformed_value: Optional[Any] = None

@dataclass
class ValidationStatistics:
    """Statistics for validation operations."""
    total: int = 0
    valid: int = 0
    invalid: int = 0
    errors_by_type: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    errors_by_field: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

class Validator:
    """Main validator using schema adapters."""
    
    def __init__(self, field_properties: Dict[str, Any]):
        """Initialize validator with field property configuration."""
        self.schema_mapping = SchemaMapping(field_properties)
        self._required_fields: Set[str] = set()
        self._cache: Dict[str, FieldAdapter] = {}
        self.stats = ValidationStatistics()
        
        # Initialize required fields from config
        self._init_required_fields(field_properties)
    
    def _init_required_fields(self, config: Dict[str, Any]) -> None:
        """Initialize set of required fields from configuration."""
        for field_type, type_config in config.items():
            for subtype, subtype_config in type_config.items():
                if isinstance(subtype_config, dict):
                    validation = subtype_config.get('validation', {})
                    if validation.get('required', False):
                        if 'fields' in subtype_config:
                            self._required_fields.update(subtype_config['fields'])
    
    def validate_field(self, field_name: str, value: Any) -> ValidationResult:
        """Validate a single field value."""
        # Handle empty values for required fields
        if self._is_empty_value(value):
            if field_name in self._required_fields:
                return ValidationResult(
                    valid=False,
                    field_name=field_name,
                    error_message=f"Required field '{field_name}' cannot be empty",
                    error_type="required_field_empty"
                )
            return ValidationResult(valid=True, field_name=field_name)
        
        # Get adapter for field type
        adapter = self._get_adapter(field_name)
        if not adapter:
            # No validation rules defined for this field
            return ValidationResult(valid=True, field_name=field_name)
        
        # Validate and transform
        is_valid, result = adapter.transform(value)
        
        # Update statistics
        self.stats.total += 1
        if is_valid:
            self.stats.valid += 1
            return ValidationResult(
                valid=True,
                field_name=field_name,
                transformed_value=result
            )
        else:
            self.stats.invalid += 1
            self.stats.errors_by_field[field_name] += 1
            error_type = "validation_error"
            self.stats.errors_by_type[error_type] += 1
            return ValidationResult(
                valid=False,
                field_name=field_name,
                error_message=str(result),
                error_type=error_type
            )
    
    def validate_record(self, record: Dict[str, Any]) -> List[ValidationResult]:
        """Validate all fields in a record."""
        results = []
        
        # Check for missing required fields
        for field_name in self._required_fields:
            if field_name not in record:
                results.append(ValidationResult(
                    valid=False,
                    field_name=field_name,
                    error_message=f"Required field '{field_name}' is missing",
                    error_type="required_field_missing"
                ))
                self.stats.invalid += 1
                self.stats.errors_by_field[field_name] += 1
                self.stats.errors_by_type["required_field_missing"] += 1
        
        # Validate present fields
        for field_name, value in record.items():
            result = self.validate_field(field_name, value)
            if not result.valid:
                results.append(result)
        
        return results
    
    def _is_empty_value(self, value: Any) -> bool:
        """Check if a value is considered empty."""
        if value is None:
            return True
        if isinstance(value, str) and not value.strip():
            return True
        return False
    
    def _get_adapter(self, field_name: str) -> Optional[FieldAdapter]:
        """Get cached adapter for a field."""
        if field_name not in self._cache:
            adapter = self.schema_mapping.get_adapter_for_field(field_name)
            if adapter:
                self._cache[field_name] = adapter
        return self._cache.get(field_name)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get current validation statistics."""
        return {
            "total_validations": self.stats.total,
            "valid_count": self.stats.valid,
            "invalid_count": self.stats.invalid,
            "validation_rate": (self.stats.valid / self.stats.total * 100 
                              if self.stats.total > 0 else 0),
            "errors_by_type": dict(self.stats.errors_by_type),
            "errors_by_field": dict(self.stats.errors_by_field)
        }
    
    def log_statistics(self) -> None:
        """Log validation statistics."""
        stats = self.get_statistics()
        logger.info("Validation Statistics:")
        logger.info(f"Total validations: {stats['total_validations']:,d}")
        logger.info(f"Valid: {stats['valid_count']:,d} ({stats['validation_rate']:.1f}%)")
        logger.info(f"Invalid: {stats['invalid_count']:,d}")
        
        if stats['errors_by_type']:
            logger.info("\nErrors by type:")
            for error_type, count in stats['errors_by_type'].items():
                logger.info(f"  {error_type}: {count:,d}")
        
        if stats['errors_by_field']:
            logger.info("\nErrors by field:")
            for field_name, count in stats['errors_by_field'].items():
                logger.info(f"  {field_name}: {count:,d}")
    
    def clear_cache(self) -> None:
        """Clear the adapter cache."""
        self._cache.clear()
        self.schema_mapping.clear_cache()