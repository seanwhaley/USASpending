"""Base validation functionality."""
from typing import Dict, Any, List, Optional, Set
from abc import ABC, abstractmethod
from threading import Lock
from datetime import datetime
import logging

from .interfaces import IFieldValidator, IValidatable

logger = logging.getLogger(__name__)


class BaseValidatable(ABC, IValidatable):
    """Base implementation of IValidatable interface."""
    
    def __init__(self):
        """Initialize validatable entity."""
        self._errors: List[str] = []
        self._is_valid: Optional[bool] = None

    def validate(self) -> bool:
        """Validate the entity."""
        self._errors.clear()
        self._is_valid = self._perform_validation()
        return self._is_valid

    @abstractmethod
    def _perform_validation(self) -> bool:
        """Perform actual validation logic.
        
        To be implemented by derived classes.
        """
        pass

    def get_validation_errors(self) -> List[str]:
        """Get validation errors."""
        return self._errors.copy()


class BaseValidator(ABC):
    """Base class for validation components."""

    def __init__(self):
        """Initialize validator."""
        self.errors: List[str] = []
        self._validation_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_lock = Lock()
        self._error_history: List[Dict[str, Any]] = []
        self._cache_stats = {
            'hits': 0,
            'misses': 0,
            'invalidations': 0
        }
        self._validation_stats = {
            'total_validations': 0,
            'failed_validations': 0,
            'validation_duration_ms': 0.0
        }
        self._max_error_history = 1000
        self._error_types: Set[str] = set()

    def add_error(self, error_message: str, error_type: Optional[str] = None,
                  context: Optional[Dict[str, Any]] = None) -> None:
        """Add an error with optional context."""
        self.errors.append(error_message)
        
        error_entry = {
            'message': error_message,
            'type': error_type or 'unknown',
            'timestamp': datetime.utcnow().isoformat(),
            'context': context
        }
        
        self._error_history.append(error_entry)
        if error_type:
            self._error_types.add(error_type)
        
        # Trim error history if needed
        while len(self._error_history) > self._max_error_history:
            self._error_history.pop(0)

    def clear_errors(self) -> None:
        """Clear current errors."""
        self.errors.clear()

    def clear_cache(self) -> None:
        """Clear validation cache."""
        with self._cache_lock:
            self._validation_cache.clear()
            self._cache_stats['invalidations'] += 1

    def get_error_summary(self) -> Dict[str, Any]:
        """Get error summary statistics."""
        error_counts = {}
        for error in self._error_history:
            error_type = error['type']
            error_counts[error_type] = error_counts.get(error_type, 0) + 1
            
        return {
            'total_errors': len(self._error_history),
            'error_types': list(self._error_types),
            'error_counts': error_counts,
            'recent_errors': self._error_history[-5:] if self._error_history else []
        }

    def get_validation_stats(self) -> Dict[str, Any]:
        """Get validation statistics."""
        avg_duration = 0.0
        if self._validation_stats['total_validations'] > 0:
            avg_duration = (self._validation_stats['validation_duration_ms'] / 
                          self._validation_stats['total_validations'])
            
        return {
            'total_validations': self._validation_stats['total_validations'],
            'failed_validations': self._validation_stats['failed_validations'],
            'success_rate': (
                (self._validation_stats['total_validations'] - 
                 self._validation_stats['failed_validations']) /
                self._validation_stats['total_validations']
                if self._validation_stats['total_validations'] > 0 else 0.0
            ),
            'average_duration_ms': avg_duration,
            'cache_stats': dict(self._cache_stats)
        }

    def _update_validation_stats(self, duration_ms: float, success: bool) -> None:
        """Update validation statistics."""
        self._validation_stats['total_validations'] += 1
        if not success:
            self._validation_stats['failed_validations'] += 1
        self._validation_stats['validation_duration_ms'] += duration_ms

    def _check_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Check if result exists in cache."""
        with self._cache_lock:
            if cache_key in self._validation_cache:
                self._cache_stats['hits'] += 1
                return self._validation_cache[cache_key]
            self._cache_stats['misses'] += 1
            return None

    def _store_in_cache(self, cache_key: str, result: Dict[str, Any]) -> None:
        """Store result in cache with timestamp."""
        with self._cache_lock:
            self._validation_cache[cache_key] = {
                **result,
                'timestamp': datetime.utcnow().isoformat()
            }