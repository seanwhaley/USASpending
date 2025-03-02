"""Enhanced validation module for USASpending data."""
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from datetime import datetime

from .validator import Validator, ValidationResult
from .logging_config import get_logger

if TYPE_CHECKING:
    from .entity_store import EntityStore

logger = get_logger(__name__)

class ValidationEngine:
    """Enhanced validation engine with integrated data validation capabilities."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize validation engine with configuration."""
        self.config = config
        self.field_properties = config.get('field_properties', {})
        self.validator = Validator(self.field_properties)
        
    def validate_record(self, record: Dict[str, Any], 
                       stores: Optional[Dict[str, 'EntityStore']] = None) -> List[ValidationResult]:
        """Validate a complete record."""
        return self.validator.validate_record(record)

    def validate_field(self, field_name: str, value: Any, rules: Dict[str, Any]) -> ValidationResult:
        """Validate a single field value."""
        return self.validator.validate_field(field_name, value)

    def get_validation_stats(self) -> Dict[str, Any]:
        """Get current validation statistics."""
        return self.validator.get_statistics()

    def log_validation_stats(self) -> None:
        """Log validation and cache statistics."""
        self.validator.log_statistics()

    def clear_cache(self) -> None:
        """Clear the validation cache."""
        self.validator.clear_cache()