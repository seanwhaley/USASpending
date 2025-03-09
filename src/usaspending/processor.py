"""Data processing functionality for converting and validating data."""
from typing import Dict, List, Any, Optional, Set, Callable, Iterator
import csv
import json
import os
from pathlib import Path
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import traceback
from contextlib import contextmanager

from . import (
    get_logger, ConfigurationError,
    create_components_from_config,
    EntityFactory, EntityStore, ValidationService,
    ensure_directory_exists as ensure_directory
)
from .interfaces import IDataProcessor, IProcessingSession, IBatchProcessor
from .config import ConfigManager
from .entity_mapper import EntityMapper 
from .file_utils import get_memory_efficient_reader, write_json_file
from .component_utils import implements
from .exceptions import ProcessingError

logger = get_logger(__name__)

@implements(IDataProcessor)
@implements(IProcessingSession)
@implements(IBatchProcessor)
class DataProcessor(IDataProcessor, IProcessingSession, IBatchProcessor):
    """Processes data records according to configured rules."""
    
    def __init__(self, config: ConfigManager, entity_mapper: EntityMapper):
        """Initialize processor with configuration and mapper."""
        self.config = config
        self.entity_mapper = entity_mapper
        self.stats: Dict[str, Any] = {
            'processed_records': 0,
            'failed_records': 0,
            'skipped_records': 0,
            'entity_counts': {},
            'start_time': None,
            'end_time': None,
            'errors_by_type': {},
            'processing_rate': 0.0,
            'batch_stats': {
                'total_batches': 0,
                'failed_batches': 0,
                'avg_batch_time': 0.0
            }
        }
        self._error_threshold = config.get_config().get('error_threshold', 1000)
        self._batch_size = config.get_config().get('batch_size', 1000)
        self._active = False
        self._error_records: List[Dict[str, Any]] = []
        self._current_batch: Optional[List[Dict[str, Any]]] = None
        self._batch_total_time = 0.0

    def start_session(self) -> None:
        """Start a processing session."""
        self._active = True
        self.stats['start_time'] = datetime.utcnow().isoformat()

    def end_session(self) -> None:
        """End a processing session."""
        self._active = False
        self.stats['end_time'] = datetime.utcnow().isoformat()
        self._update_session_stats()

    def is_active(self) -> bool:
        """Check if session is active."""
        return self._active

    def get_session_stats(self) -> Dict[str, Any]:
        """Get session statistics."""
        result_stats: Dict[str, Any] = {
            'start_time': self.stats['start_time'],
            'end_time': self.stats['end_time'],
            'duration_seconds': 0.0,
            'processing_rate': self.stats['processing_rate'],
            'batch_stats': self.stats['batch_stats'].copy()
        }
        
        # Calculate duration if session has started
        if result_stats['start_time']:
            start = datetime.fromisoformat(result_stats['start_time'])
            end = datetime.fromisoformat(result_stats['end_time'] or datetime.utcnow().isoformat())
            result_stats['duration_seconds'] = (end - start).total_seconds()
            
        return result_stats

    def _update_session_stats(self) -> None:
        """Update session-level statistics."""
        if self.stats['start_time']:
            start = datetime.fromisoformat(self.stats['start_time'])
            end = datetime.fromisoformat(self.stats['end_time'])
            duration = (end - start).total_seconds()
            if duration > 0:
                self.stats['processing_rate'] = self.stats['processed_records'] / duration
                if self.stats['batch_stats']['total_batches'] > 0:
                    self.stats['batch_stats']['avg_batch_time'] = (
                        self._batch_total_time / self.stats['batch_stats']['total_batches']
                    )

    @contextmanager
    def _processing_session(self) -> Iterator[None]:
        """Context manager for processing session stats."""
        try:
            self.start_session()
            yield
        finally:
            self.end_session()

    def process_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single record according to configured rules."""
        try:
            # Map record to entity
            entity = self.entity_mapper.map_entity(record)
            
            if not entity:
                self.stats['skipped_records'] += 1
                return {}
            
            entity_type = entity.get('entity_type')
            if entity_type:
                self.stats['entity_counts'][entity_type] = \
                    self.stats['entity_counts'].get(entity_type, 0) + 1
            
            self.stats['processed_records'] += 1
            return entity
            
        except Exception as e:
            self.stats['failed_records'] += 1
            error_type = type(e).__name__
            self.stats['errors_by_type'][error_type] = \
                self.stats['errors_by_type'].get(error_type, 0) + 1
            
            # Store error record if under threshold
            if len(self._error_records) < self._error_threshold:
                self._error_records.append({
                    'record': record,
                    'error': str(e),
                    'traceback': traceback.format_exc(),
                    'timestamp': datetime.utcnow().isoformat()
                })
            
            logger.error(f"Record processing failed: {str(e)}", exc_info=True,
                        extra={'record': record})
            return {}

    def process_batch(self, records: List[Dict[str, Any]]) -> Iterator[Dict[str, Any]]:
        """Process a batch of records."""
        if not self._active:
            with self._processing_session():
                return self._process_batch_internal(records)
        return self._process_batch_internal(records)

    def _process_batch_internal(self, records: List[Dict[str, Any]]) -> Iterator[Dict[str, Any]]:
        """Internal batch processing implementation."""
        batch_start = time.time()
        self.stats['batch_stats']['total_batches'] += 1
        self._current_batch = []
        
        try:
            for record in records:
                result = self.process_record(record)
                if result:
                    self._current_batch.append(result)
                    yield result
                
                # Check error threshold
                if self.stats['failed_records'] >= self._error_threshold:
                    logger.error(f"Error threshold ({self._error_threshold}) exceeded")
                    self.stats['batch_stats']['failed_batches'] += 1
                    break
                    
            batch_time = time.time() - batch_start
            self._batch_total_time += batch_time
            
            if self._current_batch:
                logger.debug(
                    f"Processed batch of {len(self._current_batch)} records in {batch_time:.2f}s"
                )
            
        except Exception as e:
            self.stats['batch_stats']['failed_batches'] += 1
            logger.error(f"Batch processing failed: {str(e)}", exc_info=True)
        finally:
            self._current_batch = None

    def get_processing_stats(self) -> Dict[str, Any]:
        """Get current processing statistics."""
        result_stats: Dict[str, Any] = dict(self.stats)
        mapper_stats = self.entity_mapper.get_mapping_stats()
        result_stats['mapping'] = mapper_stats
        
        # Add error records if any
        if self._error_records:
            result_stats['error_samples'] = self._error_records[:10]  # Limited sample
            
        # Add current batch info if active
        if self._current_batch:
            result_stats['current_batch'] = {
                'size': len(self._current_batch),
                'types': {
                    entity_type: len([e for e in self._current_batch 
                                    if e.get('entity_type') == entity_type])
                    for entity_type in set(e.get('entity_type') 
                                         for e in self._current_batch if e)
                }
            }
            
        return result_stats

    def initialize_batch(self) -> None:
        """Initialize a new batch processing operation.
        
        Prepares resources and state for processing a new batch of records.
        
        Raises:
            ProcessingError: If batch initialization fails
            ResourceError: If required resources are unavailable
        """
        try:
            self._current_batch = []
            self._batch_total_time = 0.0
            if not self._active:
                self.start_session()
        except Exception as e:
            logger.error(f"Failed to initialize batch: {str(e)}", exc_info=True)
            raise ProcessingError(f"Batch initialization failed: {str(e)}")

    def get_batch_stats(self) -> Dict[str, Any]:
        """Get batch processing statistics."""
        result_stats: Dict[str, Any] = self.stats['batch_stats'].copy()
        total = result_stats['total_batches']
        if total > 0:
            result_stats['success_rate'] = ((total - result_stats['failed_batches']) / total) * 100
            duration = 0.0
            if self.stats['start_time']:
                start = datetime.fromisoformat(self.stats['start_time'])
                end_time = self.stats['end_time'] or datetime.utcnow().isoformat()
                end = datetime.fromisoformat(end_time)
                duration = (end - start).total_seconds()
            result_stats['throughput'] = self.stats['processed_records'] / duration if duration > 0 else 0
            
            if self._current_batch:
                result_stats['current_batch'] = {
                    'size': len(self._current_batch),
                    'types': {
                        entity_type: len([e for e in self._current_batch 
                                        if e.get('entity_type') == entity_type])
                        for entity_type in set(e.get('entity_type') 
                                             for e in self._current_batch if e)
                    }
                }
        return result_stats

    def get_batch_errors(self) -> List[Dict[str, Any]]:
        """Get batch processing errors.
        
        Returns:
            List of error details including:
            - batch_number: Batch where error occurred
            - error: Error message
            - error_type: Type of error
            - timestamp: When error occurred
            - affected_records: Number of records affected
            - stack_trace: Optional stack trace for debugging
        """
        errors = []
        for error_record in self._error_records:
            error_detail = {
                'batch_number': self.stats['batch_stats']['total_batches'],
                'error': error_record['error'],
                'error_type': error_record.get('error_type', type(error_record['error']).__name__),
                'timestamp': error_record['timestamp'],
                'affected_records': 1,  # Individual record errors
                'stack_trace': error_record.get('traceback')
            }
            errors.append(error_detail)
        return errors

def convert_csv_to_json(config_manager: ConfigManager) -> bool:
    """Convert CSV data to JSON format using configuration."""
    try:
        # Get configuration
        config = config_manager.get_config()
        io_config = config.get('system', {}).get('io', {})
        
        # Get input/output paths
        input_path = Path(io_config.get('input', {}).get('file', ''))
        output_dir = Path(io_config.get('output', {}).get('directory', ''))
        
        if not input_path.exists():
            logger.error(f"Input file not found: {input_path}")
            return False
            
        # Ensure output directory exists
        ensure_directory(str(output_dir))
        
        # Setup batch processing
        batch_size = config.get('system', {}).get('processing', {}).get('records_per_chunk', 1000)
        
        # Create components needed for processing
        components = create_components_from_config(config)
        validation_mediator = components.get('validation_mediator')
        config_provider = components.get('config_provider')
        
        if not validation_mediator or not config_provider:
            raise ConfigurationError("Could not create required components")
            
        # Create entity mapper using configuration provider
        entity_mapper = EntityMapper(config_provider, validation_mediator)
        
        # Create processor instance using config manager directly
        processor = DataProcessor(config_manager, entity_mapper)
        
        # Create type-safe record accumulator
        entity_types = {'transaction', 'contract', 'recipient', 'agency', 'location'}
        processed_data: Dict[str, List[Dict[str, Any]]] = {
            entity_type: [] for entity_type in entity_types
        }
        
        # Set up incremental writing
        batch_count = 0
        write_threshold = 10  # Write to files every 10 batches processed
        
        # Process data in batches
        logger.info("Starting CSV to JSON conversion...")
        
        try:
            with get_memory_efficient_reader(str(input_path), batch_size=batch_size) as reader:
                for raw_batch in reader:
                    try:
                        # Convert raw batch to list of properly typed dictionaries
                        record_dicts: List[Dict[str, Any]] = []
                        
                        for raw_record in raw_batch:
                            try:
                                # Convert record to dictionary format
                                base_record: Dict[str, Any] = {}
                                
                                # Convert based on type/capabilities, with safe type checking
                                try:
                                    if not isinstance(raw_record, str):  # Avoid string dict conflict
                                        if isinstance(raw_record, dict):
                                            base_record.update(raw_record)
                                        elif hasattr(raw_record, '_asdict') and callable(getattr(raw_record, '_asdict')):
                                            base_record.update(raw_record._asdict())
                                        elif hasattr(raw_record, '__dict__'):
                                            base_record.update(vars(raw_record))
                                        elif isinstance(raw_record, (tuple, list)):
                                            fields = getattr(raw_record, '_fields', None)
                                            if fields and isinstance(fields, (tuple, list)):
                                                base_record.update(zip(map(str, fields), raw_record))
                                            else:
                                                base_record.update({str(i): v for i, v in enumerate(raw_record)})
                                    else:
                                        logger.warning(f"Skipping string record: {raw_record}")
                                        continue
                                except (TypeError, ValueError, AttributeError) as e:
                                    logger.warning(f"Record conversion error: {e}")
                                    continue

                                # Convert values to strings
                                if base_record:
                                    processed_record: Dict[str, str] = {
                                        str(k): ("" if v is None else str(v))
                                        for k, v in base_record.items()
                                    }
                                    record_dicts.append(processed_record)
                                
                            except (TypeError, ValueError, AttributeError) as e:
                                logger.warning(f"Record conversion error: {e}")
                                continue
                        
                        # Process batch and accumulate results
                        if record_dicts:
                            processed = list(processor.process_batch(record_dicts))
                            logger.info(f"Processed {len(record_dicts)} records")
                            
                            # Group by entity type
                            for result in processed:
                                entity_type = result.get('entity_type')
                                if isinstance(entity_type, str) and entity_type in processed_data:
                                    processed_data[entity_type].append(result)
                                    
                        # Increment batch count
                        batch_count += 1
                        
                        # Write all entities if threshold reached or any new entities added
                        if batch_count % write_threshold == 0:
                            logger.info("Writing all entity types to maintain consistency...")
                            for entity_type in entity_types:
                                if processed_data[entity_type]:
                                    _write_entity_files({
                                        entity_type: processed_data[entity_type]
                                    }, output_dir / 'entities', write_mode='a')
                                    processed_data[entity_type] = []  # Clear after successful write
                                
                    except Exception as e:
                        logger.error(f"Error processing batch: {str(e)}", exc_info=True)
                        continue
                        
            # Write any remaining data for all entity types
            logger.info("Writing final entities...")
            for entity_type in entity_types:
                if processed_data[entity_type]:
                    _write_entity_files({
                        entity_type: processed_data[entity_type]
                    }, output_dir / 'entities', write_mode='a')
            
            # Log final statistics
            stats = processor.get_processing_stats()
            logger.info("Processing completed with the following results:")
            logger.info(f"Total records processed: {stats['processed_records']}")
            logger.info(f"Failed records: {stats['failed_records']}")
            logger.info(f"Skipped records: {stats['skipped_records']}")
            logger.info("Entity counts:")
            for entity_type, count in stats['entity_counts'].items():
                logger.info(f"  - {entity_type}: {count} entities")
                
        except KeyboardInterrupt:
            logger.info("Process interrupted by user. Saving all accumulated data...")
            # Save all accumulated entities
            for entity_type in entity_types:
                if processed_data[entity_type]:
                    _write_entity_files({
                        entity_type: processed_data[entity_type]
                    }, output_dir / 'entities', write_mode='a')
            
            # Log partial statistics
            stats = processor.get_processing_stats()
            logger.info("Partial processing results before interruption:")
            logger.info(f"Records processed: {stats['processed_records']}")
            logger.info(f"Failed records: {stats['failed_records']}")
            logger.info("Entity counts:")
            for entity_type, count in stats['entity_counts'].items():
                logger.info(f"  - {entity_type}: {count} entities")
            raise
                
        return True
        
    except KeyboardInterrupt:
        logger.info("Process interrupted by user after saving data.")
        return True
    except Exception as e:
        logger.error(f"Conversion failed: {str(e)}", exc_info=True)
        logger.debug("Stack trace:", exc_info=True)
        return False

def _write_entity_files(processed_data: Dict[str, List[Dict[str, Any]]], 
                       output_dir: Path, write_mode: str = 'w') -> None:
    """Write entity data to JSON files."""
    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for entity_type, entities in processed_data.items():
        if entities:
            output_file = output_dir / f"{entity_type}.json"
            logger.debug(f"Writing {len(entities)} {entity_type} records to {output_file}")
            
            try:
                # Read existing content if appending
                existing_data: Dict[str, List[Dict[str, Any]]] = {entity_type: []}
                if write_mode == 'a' and output_file.exists():
                    try:
                        with open(output_file, 'r') as f:
                            existing_data = json.load(f)
                    except json.JSONDecodeError:
                        logger.warning(f"Could not read existing {output_file}, creating new file")
                
                # Combine existing and new data
                combined_data = {
                    entity_type: existing_data.get(entity_type, []) + entities
                }
                
                # Write combined data
                write_json_file(
                    str(output_file),
                    combined_data,
                    make_dirs=True
                )
                logger.info(f"Wrote {len(entities)} {entity_type} records to {output_file}")
                
                # Clear processed entities after successful write
                processed_data[entity_type] = []
                
            except Exception as e:
                logger.error(f"Error writing {entity_type} entities to {output_file}: {str(e)}")
                raise