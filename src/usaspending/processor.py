"""Enhanced data processing module with unified error handling."""
from typing import Dict, Any, Optional, List, DefaultDict, Tuple
from datetime import datetime
from collections import defaultdict
from pathlib import Path
import json
import os

from .config import ConfigManager
from .entity_factory import EntityFactory
from .entity_store import EntityStore
from .field_selector import FieldSelector
from .logging_config import get_logger
from .validation import ValidationEngine
from .chunked_writer import ChunkedWriter
from .exceptions import ProcessingError, ValidationError, EntityError
from .file_utils import (
    csv_reader, backup_file, safe_delete, ensure_directory,
    FileOperationError, FileNotFoundError
)

logger = get_logger(__name__)

class ProcessingStats:
    """Track processing statistics."""
    def __init__(self):
        self.processed = 0
        self.validation_failures = 0
        self.errors = 0
        self.start_time = datetime.now()
        self.last_time = self.start_time
        
    def log_progress(self, current_record: int, batch_size: int) -> None:
        """Log processing progress."""
        now = datetime.now()
        elapsed = (now - self.start_time).total_seconds()
        rate = current_record / elapsed if elapsed > 0 else 0
        
        # Calculate batch timing
        last_elapsed = (now - self.last_time).total_seconds()
        last_rate = batch_size / last_elapsed if last_elapsed > 0 else 0
        
        logger.info(
            f"Processed {current_record:,d} records in {elapsed:.1f}s "
            f"(avg: {rate:.1f} rec/s, current: {last_rate:.1f} rec/s)"
        )
        self.last_time = now

    def log_completion(self, writer: ChunkedWriter, stores: Dict[str, EntityStore]) -> None:
        """Log completion statistics."""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        rate = self.processed / elapsed if elapsed > 0 else 0
        
        logger.info(f"Processing completed:")
        logger.info(f"- Total records: {self.processed:,d}")
        logger.info(f"- Processing time: {elapsed:.1f}s ({rate:.1f} rec/s)")
        logger.info(f"- Validation failures: {self.validation_failures:,d}")
        logger.info(f"- Errors: {self.errors:,d}")
        logger.info(f"- Chunks created: {len(writer.chunks_info)}")
        
        # Log entity statistics
        for entity_type, store in stores.items():
            logger.info(f"\n{entity_type.title()} Statistics:")
            logger.info(f"- Unique entities: {store.stats.unique:,d}")
            if store.stats.relationships:
                logger.info("- Relationships:")
                for rel_type, count in store.stats.relationships.items():
                    logger.info(f"  {rel_type}: {count:,d}")

def process_record(record: Dict[str, Any], writer: ChunkedWriter, entity_stores: Dict[str, EntityStore], 
                  validator: Optional[ValidationEngine] = None) -> bool:
    """Process a single record with validation and error handling."""
    try:
        # Validate record if validator is present
        if validator:
            validation_results = validator.validate_record(record, entity_stores)
            invalid_results = [r for r in validation_results if not r.valid]
            if invalid_results:
                error_details = [{
                    'entity': result.field_name.split('.')[0] if '.' in result.field_name else 'unknown',
                    'field': result.field_name,
                    'message': result.message,
                    'error_type': result.error_type
                } for result in invalid_results]
                
                if not writer.config['global']['input'].get('skip_invalid_rows', False):
                    raise ValidationError(
                        f"Validation failed for record: {json.dumps(error_details, indent=2)}"
                    )
                return False

        # Process entities and relationships
        updated_record = process_entity_data(entity_stores, record, writer.config)
        writer.add_record(updated_record)
        return True
        
    except ValidationError:
        raise
    except Exception as e:
        raise ProcessingError(f"Error processing record: {str(e)}") from e

def process_entity_data(entity_stores: Dict[str, EntityStore], 
                       record: Dict[str, Any],
                       config: Dict[str, Any]) -> Dict[str, Any]:
    """Process entity extraction and relationships."""
    try:
        updated_record = record.copy()
        processed_entities = set()
        
        # Get ordered entity processing list
        processing_order = [
            (name, cfg['entity_processing'].get('processing_order', 999))
            for name, cfg in config.items()
            if isinstance(cfg, dict) and 
               'entity_processing' in cfg and 
               cfg['entity_processing'].get('enabled', False)
        ]
        processing_order.sort(key=lambda x: x[1])
        
        # Process entities in order
        for entity_type, _ in processing_order:
            if entity_type not in entity_stores:
                continue
                
            store = entity_stores[entity_type]
            try:
                entity_data = store.extract_entity_data(record)
                if entity_data:
                    if logger.isEnabledFor(logger.DEBUG):
                        logger.debug(f"Extracted {entity_type} data: {json.dumps(entity_data, indent=2)}")
                        
                    refs = store.add_entity(entity_data)
                    if refs:
                        updated_record.update(refs)
                        processed_entities.add(entity_type)
                        if logger.isEnabledFor(logger.DEBUG):
                            logger.debug(f"Added {entity_type} refs: {json.dumps(refs, indent=2)}")
                            
            except Exception as e:
                raise EntityError(f"Error processing {entity_type} entity: {str(e)}") from e
        
        return updated_record
        
    except Exception as e:
        if not config['global']['input'].get('skip_invalid_rows', False):
            raise
        logger.error(f"Error in entity processing: {str(e)}")
        return record

def save_entity_stores(stores: Dict[str, EntityStore], partial: bool = False, version: Optional[int] = None) -> None:
    """Save entity stores with error handling and backups."""
    save_errors = []
    
    for entity_type, store in stores.items():
        try:
            original = store.file_path
            backup_suffix = f".v{version}" if version else ".bak"
            
            # Create backup of existing file if it exists
            if os.path.exists(original):
                backup_path = backup_file(original, suffix=backup_suffix, max_backups=5)
                logger.debug(f"Created backup: {backup_path}")
                
            store.save()
            logger.debug(f"Saved {entity_type} store")
            
            # Only remove versioned backups after successful save
            if version:
                safe_delete(f"{original}{backup_suffix}")
                
        except Exception as e:
            error = f"Failed to save {entity_type} store: {str(e)}"
            save_errors.append(error)
            logger.error(error)
            
            # Attempt restoration from backup if available
            backup = f"{original}{backup_suffix}"
            if os.path.exists(backup):
                try:
                    os.replace(backup, original)
                    logger.info(f"Restored {entity_type} from backup")
                except Exception as restore_error:
                    logger.error(f"Failed to restore {entity_type} from backup: {str(restore_error)}")
    
    if save_errors and not partial:
        raise ProcessingError("Failed to save entity stores:\n" + "\n".join(save_errors))

def cleanup_backups(stores: Dict[str, EntityStore], max_version: int) -> None:
    """Clean up backup versions."""
    for store in stores.values():
        for version in range(1, max_version):
            backup = f"{store.file_path}.v{version}"
            try:
                safe_delete(backup)
            except Exception as e:
                logger.warning(f"Failed to remove backup: {backup}, error: {str(e)}")

def convert_csv_to_json(config_file: str) -> bool:
    """Convert CSV data to JSON with enhanced error handling and processing."""
    try:
        # Initialize configuration
        config_manager = ConfigManager(config_file)
        config = config_manager.config
        
        # Extract configuration settings
        input_config = config.get('system', {}).get('io', {}).get('input', {})
        output_config = config.get('system', {}).get('io', {}).get('output', {})
        
        input_file = input_config.get('file')
        output_dir = Path(output_config.get('directory', 'output'))
        entities_dir = output_dir / output_config.get('entities_subfolder', 'entities')
        transaction_base = output_config.get('transaction_base_name', 'transactions')
        output_path = output_dir / transaction_base

        # Create output directories
        ensure_directory(str(output_dir))
        ensure_directory(str(entities_dir))

        # Initialize validation if enabled
        validator = None
        if input_config.get('validate_input', True):
            validator = ValidationEngine(config)
            logger.info("Validation engine initialized")

        # Initialize entity stores
        entity_stores = {}
        for entity_name, entity_config in config.items():
            if isinstance(entity_config, dict) and entity_config.get('entity_processing', {}).get('enabled', False):
                try:
                    logger.info(f"Creating entity store for: {entity_name}")
                    store = EntityFactory.create_store(str(entities_dir), entity_name, config_manager)
                    if store:
                        entity_stores[entity_name] = store
                    else:
                        logger.error(f"Failed to create store for {entity_name}")
                        return False
                except Exception as e:
                    logger.error(f"Error creating entity store for {entity_name}: {str(e)}")
                    return False

        # Initialize processing components
        field_selector = FieldSelector(config)
        writer = ChunkedWriter(str(output_path), config, field_selector)
        stats = ProcessingStats()
        
        # Process CSV file
        csv_format = config.get('system', {}).get('formats', {}).get('csv', {})
        csv_encoding = csv_format.get('encoding', 'utf-8-sig')
        csv_delimiter = csv_format.get('delimiter', ',')
        csv_quotechar = csv_format.get('quotechar', '"')
        batch_size = input_config.get('batch_size', 1000)
        
        try:
            # Use the batched CSV reader from file_utils
            i = 0
            with csv_reader(
                input_file, 
                encoding=csv_encoding,
                delimiter=csv_delimiter,
                quotechar=csv_quotechar,
                batch_size=batch_size
            ) as reader:
                for batch in reader:
                    for record in batch:
                        i += 1
                        try:
                            record_valid = process_record(record, writer, entity_stores, validator)
                            if record_valid:
                                stats.processed += 1
                            else:
                                stats.validation_failures += 1
                        except (ValidationError, EntityError, ProcessingError) as e:
                            logger.error(f"Error processing record {i}: {str(e)}")
                            stats.errors += 1
                            if not input_config.get('skip_invalid_rows', False):
                                raise
                    
                    # After each batch, perform periodic operations
                    save_entity_stores(entity_stores, partial=True, version=i//batch_size)
                    stats.log_progress(i, batch_size)
        
        except FileNotFoundError:
            logger.error(f"Input file not found: {input_file}")
            return False
        except FileOperationError as e:
            logger.error(f"Error reading CSV file: {str(e)}")
            return False
                        
        # Final operations
        if writer.buffer:
            writer.write_records()
        writer.write_index()
        
        # Save and cleanup
        save_entity_stores(entity_stores)
        cleanup_backups(entity_stores, (stats.processed // batch_size) + 1)
        
        # Log final statistics
        stats.log_completion(writer, entity_stores)
        if validator:
            logger.info("\nValidation Statistics:")
            validator.log_validation_stats()
        
        return True
        
    except Exception as e:
        logger.error(f"Conversion failed: {str(e)}")
        return False