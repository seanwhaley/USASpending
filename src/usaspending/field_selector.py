"""Field selection and processing module for CSV to JSON conversion.

This module provides functionality to intelligently select and process fields
from transaction data based on priority levels defined in configuration.
"""
from typing import Dict, Any, List, Set, Optional
import logging

logger = logging.getLogger(__name__)

class FieldSelector:
    """Handles field selection based on configuration priorities."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize field selector with configuration.
        
        Args:
            config: Full application configuration dictionary
        """
        self.config = config
        self.field_config = config.get('contracts', {}).get('field_selection', {})
        self.strategy = self.field_config.get('strategy', 'all')
        
        # Build our field sets
        self.essential_fields = set(self.field_config.get('essential_fields', []))
        self.important_fields = set(self.field_config.get('important_fields', []))
        self.optional_fields = set(self.field_config.get('optional_fields', []))
        
        # Cache of selected fields for performance
        self._selected_fields_cache: Optional[Set[str]] = None
        
        logger.info(f"Field selector initialized with strategy: {self.strategy}")
        logger.info(f"Essential fields: {len(self.essential_fields)}, "
                   f"Important fields: {len(self.important_fields)}, "
                   f"Optional fields: {len(self.optional_fields)}")
    
    def get_selected_fields(self, all_field_names: List[str]) -> Set[str]:
        """Get set of field names that should be processed based on strategy.
        
        Args:
            all_field_names: Complete list of available field names in the CSV
            
        Returns:
            Set of field names that should be included based on strategy
        """
        # Return cached result if available
        if self._selected_fields_cache is not None:
            return self._selected_fields_cache
            
        if self.strategy == 'all' or not self.field_config.get('enabled', False):
            # Include all fields
            self._selected_fields_cache = set(all_field_names)
            return self._selected_fields_cache
        
        elif self.strategy == 'explicit':
            # Only include fields explicitly listed in any category
            self._selected_fields_cache = (
                self.essential_fields | 
                self.important_fields | 
                self.optional_fields
            )
            return self._selected_fields_cache
        
        elif self.strategy == 'priority':
            # Include essential, important, and all other fields as optional
            result = self.essential_fields | self.important_fields
            
            # If optional_fields is empty, include all remaining fields
            if not self.optional_fields:
                remaining_fields = set(all_field_names) - result
                result |= remaining_fields
            else:
                result |= self.optional_fields
                
            self._selected_fields_cache = result
            return result
        
        # Default to all fields if strategy not recognized
        self._selected_fields_cache = set(all_field_names)
        return self._selected_fields_cache
    
    def get_field_priority(self, field_name: str) -> str:
        """Get priority level for a given field.
        
        Args:
            field_name: Name of the field to check
            
        Returns:
            Priority level: 'essential', 'important', 'optional', or 'excluded'
        """
        if field_name in self.essential_fields:
            return 'essential'
        elif field_name in self.important_fields:
            return 'important'
        elif field_name in self.optional_fields or not self.optional_fields:
            return 'optional'
        else:
            return 'excluded'
    
    def filter_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Filter record to only include selected fields.
        
        Args:
            record: Complete record with all fields
            
        Returns:
            Filtered record with only selected fields
        """
        if self.strategy == 'all' or not self.field_config.get('enabled', False):
            return record
            
        selected_fields = self.get_selected_fields(list(record.keys()))
        
        return {
            k: v for k, v in record.items() 
            if k in selected_fields
        }