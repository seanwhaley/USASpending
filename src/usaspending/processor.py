"""Enhanced data processing module with unified error handling."""
from typing import Dict, Any, Optional, List, DefaultDict, Tuple, Type, Union
from typing_extensions import TypeAlias  # For Python < 3.10
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
from .validation import ValidationEngine, ValidationResult
from .chunked_writer import ChunkedWriter
from .exceptions import ProcessingError, ValidationError, EntityError, ConfigurationError
from .file_utils import (
    csv_reader, backup_file, safe_delete, ensure_directory,
    FileOperationError, FileNotFoundError
)
from usaspending.config import ConfigManager

# Type aliases for complex types
EntityRef: TypeAlias = Union[str, Dict[str, str]]
StoreDict: TypeAlias = Dict[str, EntityStore]

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

def process_record(record: Dict[str, Any], 
                  writer: 'ChunkedWriter', 
                  entity_stores: Dict[str, 'EntityStore'],
                  validator: Optional['ValidationEngine'] = None) -> bool:
    """Process a single record with validation and error handling."""
    try:
        logger.debug(f"Processing record with keys: {list(record.keys())}")
        
        # Validate record if validator is present
        if validator:
            logger.debug("Starting record validation")
            validation_results = validator.validate_record(record, entity_stores)
            invalid_results = [r for r in validation_results if not r.valid]
            
            if invalid_results:
                error_details = [{
                    'entity': result.field_name.split('.')[0] if '.' in result.field_name else 'unknown',
                    'field': result.field_name,
                    'message': result.error_message,
                    'error_type': result.error_type,
                    'value': record.get(result.field_name, '<not found>')
                } for result in invalid_results]
                
                logger.debug(f"Validation errors found:\n{json.dumps(error_details, indent=2)}")
                
                skip_invalid = writer.config.get('system', {}).get('io', {}).get('input', {}).get('skip_invalid_rows', False)
                if not skip_invalid:
                    error_msg = f"Validation failed for record: {json.dumps(error_details, indent=2)}"
                    logger.error(error_msg)
                    raise ValidationError(error_msg)
                    
                logger.warning(f"Skipping invalid record: {json.dumps(error_details)}")
                return False
            
            logger.debug("Record validation passed")

        # Process entities and relationships
        logger.debug("Starting entity data processing")
        updated_record = process_entity_data(entity_stores, record, writer.config)
        
        # Log any fields that were updated
        diff_fields = {k: v for k, v in updated_record.items() if k not in record or record[k] != v}
        if diff_fields:
            logger.debug(f"Fields updated during processing: {list(diff_fields.keys())}")
            
        writer.add_record(updated_record)
        logger.debug("Record successfully processed and added to writer")
        return True
        
    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing record: {str(e)}", exc_info=True)
        logger.debug(f"Failed record content:\n{json.dumps(record, indent=2)}")
        raise ProcessingError(f"Error processing record: {str(e)}") from e

def process_entity_data(entity_stores: Dict[str, 'EntityStore'], 
                       record: Dict[str, Any],
                       config: Dict[str, Any]) -> Dict[str, Any]:
    """Process entity extraction and relationships."""
    try:
        updated_record = record.copy()
        processed_entities = {}
        
        # Get ordered entity processing list from config
        entity_configs = config.get('entities', {})
        processing_order = []
        
        # Build processing order from entity configs
        for entity_type, entity_config in entity_configs.items():
            if entity_config.get('entity_processing', {}).get('enabled', True):
                order = entity_config.get('entity_processing', {}).get('processing_order', 999)
                processing_order.append((order, entity_type))
        
        # Sort by processing order
        processing_order.sort()
        logger.debug(f"Entity processing order: {[et for _, et in processing_order]}")
        
        # Process entities in order
        for order, entity_type in processing_order:
            if (entity_type not in entity_stores):
                logger.debug(f"Skipping {entity_type} - no store configured")
                continue
                
            store = entity_stores[entity_type]
            try:
                # Extract and validate entity data
                logger.debug(f"Extracting data for {entity_type}")
                entity_data = store.extract_entity_data(record)
                if not entity_data:
                    logger.debug(f"No valid data extracted for {entity_type}")
                    continue

                # Add entity to store and get reference key(s)
                logger.debug(f"Adding {entity_type} to store")
                refs = store.add_entity(entity_data)
                if not refs:
                    logger.debug(f"No references generated for {entity_type}")
                    continue
                    
                # Store processed entity info for relationship processing
                processed_entities[entity_type] = {
                    'data': entity_data,
                    'refs': refs
                }
                
                # Update record with reference(s)
                if isinstance(refs, str):
                    ref_field = f"{entity_type}_ref"
                    updated_record[ref_field] = refs
                    logger.debug(f"Added {ref_field}: {refs}")
                elif isinstance(refs, dict):
                    for k, v in refs.items():
                        ref_field = f"{entity_type}_{k}_ref"
                        updated_record[ref_field] = str(v)
                        logger.debug(f"Added {ref_field}: {v}")

                logger.debug(
                    f"Successfully processed {entity_type} entity:\n"
                    f"Data: {json.dumps(entity_data, indent=2)}\n"
                    f"Refs: {json.dumps(refs, indent=2) if isinstance(refs, dict) else refs}"
                )
                    
            except EntityError as e:
                logger.error(f"Error processing {entity_type} entity: {str(e)}", exc_info=True)
                logger.debug(f"Failed entity data: {json.dumps(record, indent=2)}")
                continue

        # Process relationships after all entities are created
        logger.debug(f"Processing relationships for entities: {list(processed_entities.keys())}")
        for entity_type, store in entity_stores.items():
            if entity_type in processed_entities:
                entity_info = processed_entities[entity_type]
                try:
                    refs = entity_info['refs']
                    entity_data = entity_info['data']
                    
                    # Create relationship context that matches store expectations
                    relationship_context = {
                        'entity_type': entity_type,
                        'current_entity': entity_data,
                        'references': {}
                    }
                    
                    # Handle both string and dictionary references
                    if isinstance(refs, str):
                        relationship_context['references']['primary'] = refs
                        logger.debug(f"Added primary reference for {entity_type}: {refs}")
                    else:
                        relationship_context['references'].update(refs)
                        logger.debug(f"Added reference mapping for {entity_type}: {refs}")
                    
                    logger.debug(f"Processing relationships for {entity_type} with context:\n{json.dumps(relationship_context, indent=2)}")
                    store.process_relationships(entity_data, relationship_context)
                    
                except Exception as e:
                    logger.error(f"Error processing relationships for {entity_type}: {str(e)}", exc_info=True)
                    logger.debug(f"Failed relationship context: {json.dumps(relationship_context, indent=2)}")
                    continue
        
        return updated_record
        
    except Exception as e:
        skip_invalid = config.get('system', {}).get('io', {}).get('input', {}).get('skip_invalid_rows', False)
        if not skip_invalid:
            raise
        logger.error(f"Error in entity processing: {str(e)}", exc_info=True)
        logger.debug(f"Failed record: {json.dumps(record, indent=2)}")
        return record

def save_entity_stores(stores: Dict[str, EntityStore], partial: bool = False, version: Optional[int] = None) -> None:
    """Save entity stores with error handling and backups.
    
    Args:
        stores: Dictionary of entity stores by type
        partial: If True, continue saving other stores when one fails
        version: Optional version number for backup files
        
    Raises:
        ProcessingError: If any stores fail to save and partial=False
    """
    save_errors = []
    
    for entity_type, store in stores.items():
        try:
            original = store.file_path
            backup_suffix = f".v{version}" if version else ".bak"
            
            # Create backup of existing file if it exists
            if os.path.exists(original):
                try:
                    backup_path = backup_file(original, suffix=backup_suffix, max_backups=5)
                    logger.debug(f"Created backup: {backup_path}")
                except FileOperationError as e:
                    logger.error(f"Failed to create backup for {entity_type}: {str(e)}")
                    if not partial:
                        raise
                
            # Attempt to save store
            try:
                store.save()
                logger.debug(f"Saved {entity_type} store")
                
                # Only remove versioned backups after successful save
                if version:
                    safe_delete(f"{original}{backup_suffix}")
                    
            except Exception as save_error:
                # Try to restore from backup
                backup = f"{original}{backup_suffix}"
                if os.path.exists(backup):
                    try:
                        os.replace(backup, original)
                        logger.info(f"Restored {entity_type} from backup")
                    except Exception as restore_error:
                        logger.error(f"Failed to restore {entity_type} from backup: {str(restore_error)}")
                
                error = f"Failed to save {entity_type} store: {str(save_error)}"
                save_errors.append(error)
                logger.error(error)
                
                if not partial:
                    raise ProcessingError(error)
                    
        except Exception as e:
            error = f"Unexpected error saving {entity_type} store: {str(e)}"
            save_errors.append(error)
            logger.error(error)
            
            if not partial:
                raise ProcessingError(error)
    
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

def convert_csv_to_json(config_manager: ConfigManager) -> bool:
    """Convert CSV data to JSON with full processing pipeline.
    
    Args:
        config_manager: Configuration manager instance
        
    Returns:
        bool: True if conversion was successful, False otherwise
    """
    try:
        config_data = config_manager.get_config()
        logger.debug(f"Starting conversion with configuration:\n{json.dumps(config_data, indent=2)}")
        
        # Extract key configuration
        system_config = config_data.get('system', {})
        io_config = system_config.get('io', {})
        input_config = io_config.get('input', {})
        output_config = io_config.get('output', {})
        processing_config = system_config.get('processing', {})
        
        input_file = Path(input_config['file'])
        output_dir = Path(output_config['directory'])
        entities_dir = output_dir / output_config.get('entities_subfolder', 'entities')
        batch_size = input_config.get('batch_size', 1000)
        
        logger.info(f"Processing input file: {input_file}")
        logger.info(f"Output directory: {output_dir}")
        logger.info(f"Entities directory: {entities_dir}")
        logger.info(f"Batch size: {batch_size}")

        if not input_file.exists():
            logger.error(f"Input file does not exist: {input_file}")
            return False

        # Create output directories
        output_dir.mkdir(parents=True, exist_ok=True)
        entities_dir.mkdir(parents=True, exist_ok=True)

        # Initialize processing components
        validator = ValidationEngine(config_data) if input_config.get('validate_input', True) else None
        writer = ChunkedWriter(
            output_dir=str(output_dir),
            config=config_data,
            chunk_size=processing_config.get('records_per_chunk', 10000),
            max_chunk_size_mb=processing_config.get('max_chunk_size_mb', 100)
        )
        factory = EntityFactory(config_data)
        entity_stores = factory.create_stores(base_path=str(entities_dir))
        stats = ProcessingStats()

        logger.info("Initialized processing pipeline components:")
        logger.info(f"- Validation enabled: {validator is not None}")
        logger.info(f"- Entity stores created: {', '.join(entity_stores.keys())}")
        
        try:
            record_count = 0
            save_frequency = processing_config.get('entity_save_frequency', 10000)
            log_frequency = processing_config.get('log_frequency', 1000)
            current_batch = []

            logger.info("Starting record processing")
            for record in csv_reader(str(input_file)):
                record_count += 1
                current_batch.append(record)
                
                # Process batch if we've reached batch size
                if len(current_batch) >= batch_size:
                    for batch_record in current_batch:
                        if process_record(batch_record, writer, entity_stores, validator):
                            stats.processed += 1
                        else:
                            stats.validation_failures += 1
                    current_batch = []
                
                # Log progress periodically
                if record_count % log_frequency == 0:
                    stats.log_progress(record_count, log_frequency)
                
                # Save entity stores periodically
                if record_count % save_frequency == 0:
                    logger.info(f"Saving entity stores at record {record_count:,d}")
                    save_entity_stores(entity_stores, partial=True)

            # Process any remaining records
            if current_batch:
                for batch_record in current_batch:
                    if process_record(batch_record, writer, entity_stores, validator):
                        stats.processed += 1
                    else:
                        stats.validation_failures += 1

            # Final save of entity stores
            logger.info("Processing complete, saving final entity stores")
            save_entity_stores(entity_stores)
            
            # Log final statistics
            stats.log_completion(writer, entity_stores)
            logger.info("Conversion completed successfully")
            return True

        except Exception as e:
            logger.error(f"Error during record processing: {str(e)}", exc_info=True)
            return False

    except KeyError as e:
        logger.error(f"Missing required configuration key: {str(e)}")
        logger.debug("Configuration error details:", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"Unexpected error during conversion: {str(e)}")
        logger.debug("Error details:", exc_info=True)
        return False