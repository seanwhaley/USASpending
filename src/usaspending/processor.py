"""Main data processing module for CSV to JSON conversion.

This module handles the core CSV to JSON conversion process, including:
- Chunked processing of large CSV files
- Entity extraction and relationship management  
- Type conversion and data cleaning
- Output file management
"""
from typing import Dict, Any, Optional, List, Set, DefaultDict
import csv
import os
import json
import logging
from datetime import datetime
from pathlib import Path
from collections import defaultdict

from .config import load_config, setup_logging
from .entity_factory import EntityFactory
from .utils import TypeConverter
from .types import ChunkInfo, EntityStats, ContractRelationshipStats
from .entity_store import EntityStore
from .recipient_store import RecipientEntityStore
from .contract_store import ContractEntityStore
from .field_selector import FieldSelector
from .validation import ValidationEngine  # Simplified import

logger = logging.getLogger(__name__)

class ChunkedWriter:
    """Manages writing records in chunks with proper data conversion."""
    
    def __init__(self, base_path: str, config: Dict[str, Any], field_selector: Optional[FieldSelector] = None, chunk_size: Optional[int] = None) -> None:
        """Initialize chunked writer.
        
        Args:
            base_path: Base path for output files
            config: Configuration dictionary
            field_selector: Optional field selector for filtering fields
            chunk_size: Optional override for chunk size
        """
        self.base_path = base_path
        self.config = config
        self.field_selector = field_selector
        
        # Initialize validator if validation is enabled
        self.validator = None
        if config['contracts']['input'].get('validate_input', True):
            self.validator = ValidationEngine(config)
            logger.debug("Validation engine initialized for ChunkedWriter")
            
            # Validate chunk configuration
            result = self.validator.validate_chunk_config(config)
            if not result.valid:
                logger.error(f"Chunk configuration error: {result.message}")
                raise ValueError(result.message)
        
        # Extract essential fields from entity configurations
        self.keep_fields = set()
        
        # Collect key_fields from each entity configuration
        for section_name, section_data in config.items():
            if isinstance(section_data, dict) and 'key_fields' in section_data:
                self.keep_fields.update(section_data['key_fields'])
            
            # Also check field_mappings for direct mappings that should be preserved
            if isinstance(section_data, dict) and 'field_mappings' in section_data:
                for mapped_field in section_data['field_mappings'].values():
                    if isinstance(mapped_field, str):
                        self.keep_fields.add(mapped_field)
                    elif isinstance(mapped_field, list):
                        self.keep_fields.update(mapped_field)
        
        # Require essential fields to be defined in config
        if not self.keep_fields:
            raise ValueError("No essential fields (key_fields) found in entity configurations")
        
        # Get processing configuration from global settings
        proc_config = config.get('global', {}).get('processing', {})
        if not proc_config:
            raise ValueError("Missing global.processing configuration section")
        
        # Set chunk size from config or override
        self.chunk_size = chunk_size or proc_config.get('records_per_chunk')
        if not self.chunk_size:
            raise ValueError("records_per_chunk required in global.processing config")
            
        # Get other processing settings
        self.max_chunk_size_mb = proc_config.get('max_chunk_size_mb')
        
        # Build excluded fields after config validation
        self.excluded_fields = self._build_excluded_fields()
        
        # Initialize type converter with full config for type mappings
        self.type_converter = TypeConverter(config)
        
        # Initialize processing state
        self.current_chunk = 1
        self.buffer: List[Dict[str, Any]] = []
        self.total_records = 0
        self.chunks_info: List[ChunkInfo] = []

    def _build_excluded_fields(self) -> Set[str]:
        """Build set of fields to exclude from processed records."""
        excluded: set[str] = set()
        
        # Get dynamic path from config
        entity_path = self.config.get('global', {}).get('entity_config_path', ['contracts', 'entity_separation', 'entities'])
        entity_config = self.config
        for path_part in entity_path:
            entity_config = entity_config.get(path_part, {})
        
        for entity_type, cfg in entity_config.items():
            if 'field_mappings' in cfg:
                # Handle both string and list field mappings
                for source_field in cfg['field_mappings'].values():
                    if isinstance(source_field, str):
                        if source_field not in self.keep_fields:
                            excluded.add(source_field)
                    elif isinstance(source_field, list):
                        excluded.update(f for f in source_field if f not in self.keep_fields)
                        
            if 'field_patterns' in cfg:
                exceptions = self.config.get('global', {}).get('field_pattern_exceptions', [])
                excluded.update(pattern for pattern in cfg['field_patterns']
                              if pattern not in exceptions)
                              
            if 'key_fields' in cfg:
                excluded.update(k for k in cfg['key_fields']
                              if k not in self.keep_fields)
        
        return excluded

    def clean_record_for_chunk(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Clean record for chunking by removing excluded fields."""
        if self.validator:
            return self.validator.validate_clean_record(record, self.keep_fields, self.excluded_fields)
            
        # Fallback for when validation is disabled
        cleaned: Dict[str, Any] = {}
        for key, value in record.items():
            if (key in self.keep_fields or
                not any(key.startswith(pattern) for pattern in self.excluded_fields) or
                key.endswith('_ref')):
                cleaned[key] = value
        return cleaned

    def write_records(self) -> None:
        """Write buffered records to chunk file with atomic operations."""
        if not self.buffer:
            return
            
        chunk_file = f"{self.base_path}_part{self.current_chunk}.json"
        temp_file = f"{chunk_file}.tmp"
        backup_file = f"{chunk_file}.bak"
        
        try:
            # Clean records - validation ensures all essential fields exist
            cleaned_records = [self.clean_record_for_chunk(record) for record in self.buffer]
            
            # Create chunk data with metadata
            chunk_data = {
                "metadata": {
                    "chunk_number": self.current_chunk,
                    "record_count": len(cleaned_records),
                    "generated_date": datetime.now().isoformat()
                },
                "records": cleaned_records
            }
            
            # Ensure output directory exists
            os.makedirs(os.path.dirname(self.base_path), exist_ok=True)
            
            # Create backup if chunk exists
            if os.path.exists(chunk_file):
                os.replace(chunk_file, backup_file)
            
            # Write to temp file first
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(chunk_data, f, indent=2, ensure_ascii=False)
                
            # Atomic rename to final file
            os.replace(temp_file, chunk_file)
            
            # Update tracking
            self.chunks_info.append(ChunkInfo(
                file=chunk_file,
                record_count=len(cleaned_records),
                chunk_number=self.current_chunk
            ))
            
            self.total_records += len(cleaned_records)
            self.current_chunk += 1
            self.buffer = []
            
            # Remove backup after successful write
            if os.path.exists(backup_file):
                os.remove(backup_file)
                
        except Exception as e:
            logger.error(f"Error writing chunk {self.current_chunk}: {str(e)}")
            # Restore from backup if available
            if os.path.exists(backup_file):
                os.replace(backup_file, chunk_file)
            raise

    def write_index(self) -> None:
        """Write index file with chunk metadata."""
        index_file = f"{self.base_path}_index.json"
        temp_file = f"{index_file}.tmp"
        
        try:
            index_data = {
                "metadata": {
                    "total_records": self.total_records,
                    "total_chunks": len(self.chunks_info),
                    "generated_date": datetime.now().isoformat()
                },
                "chunks": [
                    {
                        "file": os.path.basename(chunk.file),
                        "record_count": chunk.record_count,
                        "chunk_number": chunk.chunk_number
                    }
                    for chunk in self.chunks_info
                ]
            }
            
            # Write to temp file first
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(index_data, f, indent=2, ensure_ascii=False)
                
            # Atomic rename
            os.replace(temp_file, index_file)
            
        except Exception as e:
            logger.error(f"Error writing index file: {str(e)}")
            raise

def process_entity_data(entity_stores: Dict[str, EntityStore], 
                       record: Dict[str, Any],
                       config: Dict[str, Any]) -> Dict[str, Any]:
    """Process entity extraction and add references to the record."""
    updated_record = record.copy()
    processed_entities = set()
    
    # Get the ordered entity names (using the same logic as in convert_csv_to_json)
    processing_order = []
    for entity_name, entity_config in config.items():
        if isinstance(entity_config, dict) and 'entity_processing' in entity_config:
            proc_config = entity_config['entity_processing']
            if proc_config.get('enabled', False):
                order = proc_config.get('processing_order', 999)
                processing_order.append((entity_name, order))
    
    # Sort entities by processing order
    processing_order.sort(key=lambda x: x[1])
    ordered_entities = [name for name, _ in processing_order]
    
    for entity_type in ordered_entities:
        if entity_type not in entity_stores:
            continue
            
        store = entity_stores[entity_type]
        try:
            # Extract and add entity, get back reference details
            entity_data = store.extract_entity_data(record)
            if entity_data:
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"Extracted {entity_type} data: {json.dumps(entity_data, indent=2)}")
                    
                refs = store.add_entity(entity_data)
                if refs:
                    updated_record.update(refs)
                    processed_entities.add(entity_type)
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(f"Added {entity_type} refs: {json.dumps(refs, indent=2)}")
                        
            else:
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"No {entity_type} data extracted from record")
                    
        except Exception as e:
            logger.error(f"Error processing {entity_type} entity: {str(e)}")
            logger.debug("Record data:", exc_info=True)
            if not config['contracts']['input'].get('skip_invalid_rows', False):
                raise
    
    return updated_record

def _save_entity_stores(stores: Dict[str, EntityStore], partial: bool = False, version: Optional[int] = None) -> None:
    """Save entity stores with proper error handling."""
    save_errors = []
    
    for entity_type, store in stores.items():
        try:
            original = store.file_path
            backup = f"{original}.v{version}" if version else f"{original}.bak"
            
            # Create backup of existing file
            if os.path.exists(original):
                os.replace(original, backup)
                
            store.save()
            logger.debug(f"Saved {entity_type} store")
            
            # Remove backup after successful save
            if os.path.exists(backup):
                os.remove(backup)
                
        except Exception as e:
            error = f"Failed to save {entity_type} store: {str(e)}"
            save_errors.append(error)
            logger.error(error)
            
            # Restore from backup if available
            if version and os.path.exists(backup):
                try:
                    os.replace(backup, original)
                    logger.info(f"Restored {entity_type} from backup")
                except:
                    logger.error(f"Failed to restore {entity_type} from backup")
    
    if save_errors and not partial:
        raise RuntimeError("Failed to save entity stores:\n" + "\n".join(save_errors))

def _cleanup_backups(stores: Dict[str, EntityStore], max_version: int) -> None:
    """Clean up backup versions after successful processing."""
    for store in stores.values():
        for version in range(1, max_version):
            backup = f"{store.file_path}.v{version}"
            try:
                if os.path.exists(backup):
                    os.remove(backup)
            except Exception as e:
                logger.warning(f"Failed to remove backup: {backup}, error: {str(e)}")

def process_record(record: Dict[str, Any], writer: ChunkedWriter, entity_stores: Dict[str, EntityStore], 
                  validator: Optional[ValidationEngine] = None, validation_results: Optional[List[Any]] = None) -> bool:
    """Process a single record through the pipeline.
    
    Args:
        record: The record to process
        writer: The ChunkedWriter instance
        entity_stores: Dictionary of entity stores
        validator: Optional validation engine
        validation_results: Optional precomputed validation results
        
    Returns:
        True if the record was valid and processed, False otherwise
    """
    validation_errors = []
    
    # Validate record if validator is provided and no precomputed results
    if validator and validation_results is None:
        validation_results = validator.validate_record(record, entity_stores)
    
    if validation_results:
        invalid_results = [r for r in validation_results if not r.valid]
        if invalid_results:
            for result in invalid_results:
                validation_errors.append({
                    'entity': result.field_name.split('.')[0] if '.' in result.field_name else 'unknown',
                    'field': result.field_name,
                    'message': result.message,
                    'error_type': result.error_type
                })
    
    valid_record = not validation_errors
    
    # If validation failed and skip_invalid_rows is False, raise an error
    if not valid_record and not writer.config['contracts']['input'].get('skip_invalid_rows', False):
        error_message = f"Validation failed for record: {json.dumps(validation_errors, indent=2)}"
        logger.error(error_message)
        raise ValueError(error_message)
    
    # Only process valid records or if skip_invalid_rows is True
    if valid_record or writer.config['contracts']['input'].get('skip_invalid_rows', False):
        # Process record using entity stores and maintain entity relationships
        updated_record = process_entity_data(entity_stores, record, writer.config)
        
        # Add to chunk
        writer.buffer.append(updated_record)
        if len(writer.buffer) >= writer.chunk_size:
            writer.write_records()
            
        return valid_record
    
    return False

def _log_progress(records: int, start_time: datetime, last_time: datetime, frequency: int) -> None:
    """Log processing progress."""
    now = datetime.now()
    elapsed = (now - start_time).total_seconds()
    rate = records / elapsed if elapsed > 0 else 0
    
    # Calculate timing metrics
    last_elapsed = (now - last_time).total_seconds()
    last_rate = frequency / last_elapsed if last_elapsed > 0 else 0
    
    logger.info(
        f"Processed {records:,d} records in {elapsed:.1f}s "
        f"(avg: {rate:.1f} rec/s, current: {last_rate:.1f} rec/s)"
    )

def _log_completion(records: int, start_time: datetime, 
                   writer: ChunkedWriter, stores: Dict[str, EntityStore]) -> None:
    """Log completion statistics."""
    elapsed = (datetime.now() - start_time).total_seconds()
    rate = records / elapsed if elapsed > 0 else 0
    
    logger.info(f"Completed processing {records:,d} records in {elapsed:.1f}s ({rate:.1f} rec/s)")
    logger.info(f"Created {len(writer.chunks_info)} chunks")
    
    # Log entity stats
    for entity_type, store in stores.items():
        logger.info(f"{entity_type.title()} entities: {store.stats.unique:,d}")
        if isinstance(store, ContractEntityStore):
            rel_stats = store.relationship_stats.to_dict()
            logger.info("Contract relationships:")
            for rel_type, count in rel_stats.items():
                logger.info(f"  {rel_type}: {count:,d}")

def convert_csv_to_json(config_file: str) -> bool:
    """Convert CSV to JSON using configuration settings."""
    logger = logging.getLogger(__name__)
    
    try:
        # Load and validate config
        config = load_config(config_file)
        input_file = config['contracts']['input']['file']
        output_dir = config['global']['output']['directory']
        entities_dir = os.path.join(output_dir, config['global']['output']['entities_subfolder'])
        transaction_base = config['global']['output']['transaction_base_name']
        output_path = os.path.join(output_dir, transaction_base)
        
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(entities_dir, exist_ok=True)
        
        validator = None
        if config['contracts']['input'].get('validate_input', True):
            validator = ValidationEngine(config)
            logger.info("Validation engine initialized")
        
        entity_configs = {}
        for entity_name, entity_config in config.items():
            if isinstance(entity_config, dict) and entity_config.get('entity_type', False):
                result = validator.validate_entity_config(entity_name, entity_config)
                if not result.valid:
                    logger.error(f"Entity config validation error: {result.message}")
                    return False
                if entity_config.get('entity_processing', {}).get('enabled', False):
                    entity_configs[entity_name] = entity_config
        
        order_results = validator.validate_processing_order(entity_configs)
        invalid_results = [r for r in order_results if not r.valid]
        if invalid_results:
            for result in invalid_results:
                logger.error(f"Processing order validation error: {result.message}")
            return False

        with open(input_file, 'r', encoding=config['global']['encoding']) as csvfile:
            headers = next(csv.reader(csvfile), [])
            result = validator.validate_csv_structure(headers)
            if not result.valid:
                logger.error(f"CSV validation error: {result.message}")
                return False

        field_selector = FieldSelector(config)
        writer = ChunkedWriter(output_path, config, field_selector)
        stats: DefaultDict[str, int] = defaultdict(int)
        start_time = datetime.now()
        last_time = start_time

        validation_results = {}
        with open(input_file, 'r', encoding=config['global']['encoding']) as csvfile:
            reader = csv.DictReader(csvfile)
            batch_size = config['contracts']['input']['batch_size']
            
            entity_stores = {}
            for entity_name, entity_config in entity_configs.items():
                store_type = entity_config['entity_processing']['store_type']
                logger.info(f"Creating entity store for: {entity_name} (type: {store_type})")
                entity_stores[entity_name] = EntityFactory.create_store(store_type, entities_dir, config)
            
            for i, record in enumerate(reader, 1):
                try:
                    if validator:
                        validation_results[i] = validator.validate_record(record, entity_stores)
                    
                    record_valid = process_record(record, writer, entity_stores, validator, validation_results.get(i))
                    if record_valid:
                        stats['processed'] += 1
                    else:
                        stats['validation_failures'] += 1
                        logger.warning(f"Record {i} failed validation")
                    
                    if i % batch_size == 0:
                        _save_entity_stores(entity_stores, partial=True, version=i//batch_size)
                        _log_progress(i, start_time, last_time, batch_size)
                        last_time = datetime.now()
                        
                except Exception as e:
                    logger.error(f"Error processing record {i}: {str(e)}")
                    stats['errors'] += 1
                    if not config['contracts']['input'].get('skip_invalid_rows', False):
                        raise
            
            if writer.buffer:
                writer.write_records()
                
            writer.write_index()
            EntityFactory.link_entities(entity_stores)
            _save_entity_stores(entity_stores)
            _log_completion(stats['processed'], start_time, writer, entity_stores)
            
            if validator:
                logger.info(f"Validation statistics:")
                # Log validation statistics here
            
            return True
            
    except Exception as e:
        logger.error(f"Conversion failed: {str(e)}")
        return False