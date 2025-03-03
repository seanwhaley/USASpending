"""Key type implementations for entity identification."""
from typing import Dict
import json

class CompositeKey:
    """Hashable wrapper for composite entity keys."""
    def __init__(self, key_dict: Dict[str, str]):
        self._key = frozenset(sorted(key_dict.items()))
        self._dict = dict(key_dict)
        
    def __hash__(self):
        return hash(self._key)
        
    def __eq__(self, other):
        if isinstance(other, CompositeKey):
            return self._key == other._key
        return False
        
    def __str__(self):
        return json.dumps(self._dict, sort_keys=True)
        
    def to_dict(self) -> Dict[str, str]:
        return dict(self._dict)