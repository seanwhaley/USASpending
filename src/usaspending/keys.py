"""Key type implementations for entity identification.

This module provides classes for creating and managing unique identifiers for entities
in the USASpending data. These keys are designed to be hashable and comparable.
"""
from typing import Dict, Any
import json

class KeyValidationError(Exception):
    """Exception raised for key validation errors."""
    pass

class CompositeKey:
    """A composite key made up of multiple string key-value pairs."""
    
    def __init__(self, key_dict: Dict[str, str]):
        """Initialize a CompositeKey from a dictionary.
        
        Args:
            key_dict: Dictionary of string key-value pairs that identify an entity.
                      All keys and values must be strings.
        
        Raises:
            KeyValidationError: If key_dict is not a dictionary, is empty, or contains non-string keys or values.
        """
        if not isinstance(key_dict, dict):
            raise KeyValidationError("key_dict must be a dictionary")
        if not key_dict:
            raise KeyValidationError("key_dict cannot be empty")
        if not all(isinstance(k, str) and isinstance(v, str) for k, v in key_dict.items()):
            raise KeyValidationError("All keys and values must be strings")
            
        self._key = frozenset(sorted(key_dict.items()))
        self._dict = dict(key_dict)

    def __hash__(self) -> int:
        """Get hash value for the composite key.
        
        Returns:
            Hash value based on the frozen set of key-value pairs
        """
        return hash(self._key)
        
    def __eq__(self, other: Any) -> bool:
        """Check if two composite keys are equal.
        
        Args:
            other: Another object to compare with
            
        Returns:
            True if other is a CompositeKey with the same key-value pairs
        """
        if isinstance(other, CompositeKey):
            return self._key == other._key
        return False
        
    def __str__(self) -> str:
        """Get string representation of the key.
        
        Returns:
            JSON string of the key-value pairs, sorted by key
        """
        return json.dumps(self._dict, sort_keys=True)
        
    def to_dict(self) -> Dict[str, str]:
        """Convert key to dictionary representation.
        
        Returns:
            Dictionary containing the key fields and values
        """
        return dict(self._dict)