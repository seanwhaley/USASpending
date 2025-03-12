"""Core data processing functionality."""
from contextlib import contextmanager
import time
from typing import Dict, Any, List, Optional, Iterator, cast
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from .interfaces import (
    IProcessor,
    IEntityMapper,
    IValidationService,
    IEntityStore,
    IConfigurable
)
from .types import EntityData, EntityType, ComponentConfig
from .exceptions import ProcessingError
from .utils import chunk_list, Timer

@dataclass
class ProcessingStats:
    """Processing statistics."""
    total_records: int = 0
    processed_records: int = 0
    failed_records: int = 0
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    validation_errors: List[str] = field(default_factory=list)
    mapping_errors: List[str] = field(default_factory=list)
    entity_counts: Dict[str, int] = field(default_factory=dict)

class DataProcessor(IProcessor, IConfigurable):
    """Main data processing coordinator."""

    def __init__(self, mapper: IEntityMapper, validator: IValidationService, store: IEntityStore):
        """Initialize processor with required components."""
        self.mapper = mapper
        self.validator = validator
        self.store = store
        self._config: Dict[str, Any] = {}
        self._entity_configs: Dict[str, Dict[str, Any]] = {}
        self._initialized = False
        self.stats = ProcessingStats()
    
    @contextmanager
    def _get_executor(self, max_workers: int) -> Iterator[ThreadPoolExecutor]:
        """Context manager for thread pool executor."""
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            yield executor
            
    def configure(self, config: ComponentConfig) -> None:
        """Configure processor.
        
        Args:
            config: Component configuration containing settings and entities
        """
        if not config or not isinstance(config, ComponentConfig):
            raise ProcessingError("Valid ComponentConfig required")
            
        self._config = config.settings or {}
        self._executor = ThreadPoolExecutor(
            max_workers=self._config.get("max_workers", 4)
        )
        self._entity_configs = self._config.get("entities", {})
        self.stats = ProcessingStats()
        self.stats.start_time = time.time()
        self._initialized = True
        
    def process_batch(self, records: List[Dict[str, Any]], batch_size: Optional[int] = None) -> List[Dict[str, Any]]:
        """Process a batch of records.
        
        Args:
            records: List of records to process
            batch_size: Optional override for configured batch size
            
        Returns:
            List of processed records
        """
        if not self._initialized:
            raise ProcessingError("Processor not configured")
            
        effective_batch_size = batch_size or self._config.get("batch_size", 1000)
        results = []
        max_workers = self._config.get("max_workers", 4)
        
        try:
            with self._get_executor(max_workers) as executor:
                # Process records in chunks
                for chunk in chunk_list(records, effective_batch_size):
                    futures = []
                    
                    # Submit processing tasks
                    for record in chunk:
                        future = executor.submit(self._process_record, record)
                        futures.append(future)
                        
                    # Collect results
                    for future in futures:
                        try:
                            if result := future.result():
                                results.append(result)
                        except Exception as e:
                            self.stats.failed_records += 1
                            self.stats.validation_errors.append(str(e))
        except Exception as e:
            self.stats.end_time = time.time()
            raise ProcessingError(f"Batch processing failed: {str(e)}") from e
            
        self.stats.end_time = time.time()
        return results

    def _process_record(self, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a single record."""
        self.stats.total_records += 1
        
        try:
            # Get potential entity types in processing order
            entity_types = sorted(
                [(name, cfg.get("processing", {}).get("processing_order", 999)) 
                 for name, cfg in self._entity_configs.items()],
                key=lambda x: x[1]
            )
            
            # Try processing as each entity type in order
            for entity_type, _ in entity_types:
                if self._matches_entity_definition(record, entity_type):
                    return self._process_as_entity(record, entity_type)
            
            raise ProcessingError("Record does not match any entity definition")
                
        except Exception as e:
            self.stats.failed_records += 1
            error_msg = f"Record processing failed: {str(e)}"
            self.stats.validation_errors.append(error_msg)
            return None
            
    def process_stream(self, records: Iterator[Dict[str, Any]]) -> Iterator[Dict[str, Any]]:
        """Process records as a stream."""
        if not self._initialized:
            raise ProcessingError("Processor not configured")
            
        batch: List[Dict[str, Any]] = []
        batch_size = self._config.get("batch_size", 1000)
        
        for record in records:
            batch.append(record)
            
            if len(batch) >= batch_size:
                yield from self.process_batch(batch)
                batch = []
                
        if batch:
            yield from self.process_batch(batch)
            
    def get_stats(self) -> Dict[str, Any]:
        """Get processing statistics."""
        with Timer() as timer:
            stats = {
                "total_records": self.stats.total_records,
                "processed_records": self.stats.processed_records,
                "failed_records": self.stats.failed_records,
                "processing_time": timer.elapsed,
                "entity_counts": self.stats.entity_counts,
                "error_count": len(self.stats.validation_errors),
                "errors": self.stats.validation_errors[-100:]  # Last 100 errors
            }
        return stats
        
    def _matches_entity_definition(self, record: Dict[str, Any], entity_type: str) -> bool:
        """Check if record matches entity definition from config."""
        entity_config = self._entity_configs.get(entity_type, {})
        
        # Check key fields
        key_fields = entity_config.get("key_fields", [])
        if not all(field in record for field in key_fields):
            return False
            
        # Check field mappings
        field_mappings = entity_config.get("field_mappings", {})
        
        # Check direct mappings
        direct_mappings = field_mappings.get("direct", {})
        if any(target in record for target in direct_mappings.values()):
            return True
            
        # Check multi-source mappings
        multi_source = field_mappings.get("multi_source", {})
        for mapping in multi_source.values():
            sources = mapping.get("sources", [])
            if any([source in record for source in sources]):
                return True
                
        return False
        
    def _process_as_entity(self, record: Dict[str, Any], entity_type: str) -> Optional[Dict[str, Any]]:
        """Process record as specific entity type."""
        # Map record to entity
        entity_data = self.mapper.map_entity(cast(EntityType, entity_type), record)
        if not entity_data:
            self.stats.mapping_errors.extend(self.mapper.get_errors())
            raise ProcessingError("Entity mapping failed")
            
        # Validate entity
        if not self.validator.validate(cast(EntityType, entity_type), entity_data):
            self.stats.validation_errors.extend(self.validator.get_validation_errors())
            raise ProcessingError("Entity validation failed")
            
        # Store entity
        result = self.store.save_entity(cast(EntityType, entity_type), cast(EntityData, entity_data))
        if not result:
            raise ProcessingError("Entity storage failed")
            
        # Update stats
        self.stats.processed_records += 1
        self.stats.entity_counts[entity_type] = \
            self.stats.entity_counts.get(entity_type, 0) + 1
            
        return entity_data
        
    def cleanup(self) -> None:
        """Clean up resources."""
        if hasattr(self, '_executor'):
            self._executor.shutdown(wait=True)
        self.stats.end_time = time.time()
        self.stats = ProcessingStats()
        self._initialized = False

__all__ = [
    'ProcessingStats',
    'DataProcessor'
]