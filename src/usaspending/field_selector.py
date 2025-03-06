"""Field selection and extraction system."""
from typing import Dict, Any, List, Set, Optional
from dataclasses import dataclass
import re

from .interfaces import IFieldSelector
from .logging_config import get_logger

logger = get_logger(__name__)

@dataclass
class FieldPath:
    """Represents a field path with array indexing."""
    path: str
    array_indices: Dict[str, int]

class FieldSelector(IFieldSelector):
    """Handles field selection and extraction from data."""
    
    def __init__(self, field_mappings: Dict[str, str],
                 array_fields: Optional[Dict[str, str]] = None):
        """Initialize selector with field mappings."""
        self.field_mappings = field_mappings
        self.array_fields = array_fields or {}
        self.available_fields = set(field_mappings.values())
        
    def select_fields(self, data: Dict[str, Any],
                     field_names: List[str]) -> Dict[str, Any]:
        """Select specific fields from data."""
        result = {}
        
        for field_name in field_names:
            if field_name in self.field_mappings:
                source_path = self.field_mappings[field_name]
                value = self._extract_field(data, source_path)
                if value is not None:
                    result[field_name] = value
                    
        return result
        
    def get_available_fields(self) -> List[str]:
        """Get list of available fields."""
        return sorted(self.available_fields)
        
    def _extract_field(self, data: Dict[str, Any], path: str) -> Any:
        """Extract field value using dot notation path."""
        # Parse field path
        field_path = self._parse_field_path(path)
        
        # Navigate through data
        current = data
        path_parts = field_path.path.split('.')
        
        for part in path_parts[:-1]:
            base_part = part.split('[')[0]
            
            if base_part not in current:
                return None
                
            current = current[base_part]
            
            # Handle array indexing
            if base_part in field_path.array_indices:
                try:
                    index = field_path.array_indices[base_part]
                    if not isinstance(current, list) or index >= len(current):
                        return None
                    current = current[index]
                except (IndexError, TypeError):
                    return None
                    
        # Get final value
        final_part = path_parts[-1]
        base_part = final_part.split('[')[0]
        
        if base_part not in current:
            return None
            
        value = current[base_part]
        
        # Handle array indexing for final part
        if base_part in field_path.array_indices:
            try:
                index = field_path.array_indices[base_part]
                if not isinstance(value, list) or index >= len(value):
                    return None
                value = value[index]
            except (IndexError, TypeError):
                return None
                
        return value
        
    def _parse_field_path(self, path: str) -> FieldPath:
        """Parse field path with array indexing."""
        array_indices = {}
        clean_path = ""
        current_part = ""
        
        i = 0
        while i < len(path):
            if path[i] == '[':
                # Start of array index
                part_name = current_part.split('.')[-1]
                i += 1
                index_str = ""
                while i < len(path) and path[i] != ']':
                    index_str += path[i]
                    i += 1
                try:
                    array_indices[part_name] = int(index_str)
                except ValueError:
                    logger.warning(f"Invalid array index in path: {path}")
                i += 1  # Skip closing bracket
            else:
                current_part += path[i]
                if path[i] == '.' or i == len(path) - 1:
                    clean_path += current_part
                    current_part = ""
                i += 1
                
        return FieldPath(
            path=clean_path,
            array_indices=array_indices
        )
        
    def add_field_mapping(self, field_name: str,
                         source_path: str) -> None:
        """Add new field mapping."""
        self.field_mappings[field_name] = source_path
        self.available_fields.add(field_name)
        
    def remove_field_mapping(self, field_name: str) -> None:
        """Remove field mapping."""
        if field_name in self.field_mappings:
            del self.field_mappings[field_name]
            self.available_fields.remove(field_name)
            
    def get_field_source(self, field_name: str) -> Optional[str]:
        """Get source path for field."""
        return self.field_mappings.get(field_name)
        
    def get_array_field_info(self, field_name: str) -> Optional[str]:
        """Get array field information."""
        return self.array_fields.get(field_name)
        
    def is_array_field(self, field_name: str) -> bool:
        """Check if field is an array field."""
        return field_name in self.array_fields