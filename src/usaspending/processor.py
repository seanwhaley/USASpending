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
        # Validate record if validator is present
        if validator:
            validation_results = validator.validate_record(record, entity_stores)
            invalid_results = [r for r in validation_results if not r.valid]
            if invalid_results:
                error_details = [{
                    'entity': result.field_name.split('.')[0] if '.' in result.field_name else 'unknown',
                    'field': result.field_name,
                    'message': result.error_message,  # Use error_message instead of message
                    'error_type': result.error_type
                } for result in invalid_results]
                
                # Check config safely
                skip_invalid = writer.config.get('system', {}).get('io', {}).get('input', {}).get('skip_invalid_rows', False)
                if not skip_invalid:
                    raise ValidationError(
                        f"Validation failed for record: {json.dumps(error_details, indent=2)}"
                    )
                logger.warning(f"Skipping invalid record: {json.dumps(error_details)}")
                return False

        # Process entities and relationships
        updated_record = process_entity_data(entity_stores, record, writer.config)
        writer.add_record(updated_record)
        return True
        
    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing record: {str(e)}", exc_info=True)
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
        
        # Process entities in order
        for order, entity_type in processing_order:
            if (entity_type not in entity_stores):
                continue
                
            store = entity_stores[entity_type]
            try:
                # Extract and validate entity data
                entity_data = store.extract_entity_data(record)
                if not entity_data:
                    continue

                # Add entity to store and get reference key(s)
                refs = store.add_entity(entity_data)
                if not refs:
                    continue
                    
                # Store processed entity info for relationship processing
                processed_entities[entity_type] = {
                    'data': entity_data,
                    'refs': refs
                }
                
                # Update record with reference(s)
                if isinstance(refs, str):
                    updated_record[f"{entity_type}_ref"] = refs
                elif isinstance(refs, dict):
                    for k, v in refs.items():
                        updated_record[f"{entity_type}_{k}_ref"] = str(v)

                logger.debug(
                    f"Processed {entity_type} entity:\n"
                    f"Data: {json.dumps(entity_data, indent=2)}\n"
                    f"Refs: {json.dumps(refs, indent=2) if isinstance(refs, dict) else refs}"
                )
                    
            except EntityError as e:
                logger.error(f"Error processing {entity_type} entity: {str(e)}")
                continue

        # Process relationships after all entities are created
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
                    else:
                        relationship_context['references'].update(refs)
                    
                    store.process_relationships(entity_data, relationship_context)
                    
                except Exception as e:
                    logger.error(f"Error processing relationships for {entity_type}: {str(e)}")
                    continue
        
        return updated_record
        
    except Exception as e:
        skip_invalid = config.get('system', {}).get('io', {}).get('input', {}).get('skip_invalid_rows', False)
        if not skip_invalid:
            raise
        logger.error(f"Error in entity processing: {str(e)}")
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

def convert_csv_to_json(config_manager) -> bool:
    """Convert CSV data to JSON output using the provided configuration.
    
    Args:
        config_manager: A ConfigManager instance or compatible object
                       that provides configuration access
    
    Returns:
        bool: True if conversion succeeded, False otherwise
    """
    try:
        try:
            config = config_manager.get_config()
            # Validate required config sections
            if 'system' not in config:
                raise ConfigurationError("Missing 'system' configuration section")
            if 'io' not in config['system']:
                raise ConfigurationError("Missing 'system.io' configuration section")
            if 'input' not in config['system']['io']:
                raise ConfigurationError("Missing 'system.io.input' configuration section")
            if 'output' not in config['system']['io']:
                raise ConfigurationError("Missing 'system.io.output' configuration section")
            if 'processing' not in config['system']:
                raise ConfigurationError("Missing 'system.processing' configuration section")
            if 'formats' not in config['system']:
                raise ConfigurationError("Missing 'system.formats' configuration section")
        except ConfigurationError as e:
            logger.error(f"Failed to load configuration: {e}")
            raise ProcessingError("Configuration error") from e
        except Exception as e:
            logger.error(f"Failed to access configuration: {str(e)}")
            raise ProcessingError(f"Configuration access error: {str(e)}") from e

        system_config = config['system']
        input_config = system_config['io']['input']
        output_config = system_config['io']['output']
        
        input_file = Path(input_config['file'])
        output_dir = Path(output_config['directory'])

        # Check if input file exists
        if not input_file.exists():
            logger.error(f"Input file does not exist: {input_file}")
            return False

        # Initialize components
        validator = ValidationEngine(config)
        entity_factory = EntityFactory(config)

        # Create the base output path using output directory
        output_base = output_dir / output_config.get('base_filename', 'output')
        writer = ChunkedWriter(output_base, config)
        stats = ProcessingStats()

        # Create output directory if it doesn't exist
        ensure_directory(output_dir)
        ensure_directory(output_dir / output_config.get('entities_subfolder', 'entities'))

        # Initialize entity stores
        stores = {}
        for entity_type, entity_config in config_manager.get_entity_configs().items():
            if entity_config.get('entity_processing', {}).get('enabled', True):
                stores[entity_type] = entity_factory.create_store(entity_type)

        # Process records
        batch_size = input_config.get('batch_size', 1000)
        with csv_reader(input_file, 
                       encoding=system_config['formats']['csv'].get('encoding', 'utf-8'),
                       delimiter=system_config['formats']['csv'].get('delimiter', ','),
                       quotechar=system_config['formats']['csv'].get('quotechar', '"')) as reader:
            for i, record in enumerate(reader, 1):
                try:
                    if process_record(record, writer, stores, validator):
                        stats.processed += 1
                    else:
                        stats.validation_failures += 1
                except ValidationError as ve:
                    stats.validation_failures += 1
                    logger.warning(f"Validation error in record {i}: {str(ve)}")
                except Exception as e:
                    stats.errors += 1
                    logger.error(f"Error processing record {i}: {str(e)}")

                # Progress logging
                if i % batch_size == 0:
                    stats.log_progress(i, batch_size)

                # Save entity stores periodically
                if i % system_config['processing']['entity_save_frequency'] == 0:
                    save_entity_stores(stores, partial=True, version=i)

        # Final saves and cleanup
        writer.close()
        save_entity_stores(stores)
        cleanup_backups(stores, max_version=5)

        # Log completion statistics
        stats.log_completion(writer, stores)
        return True

    except Exception as e:
        logger.error(f"Conversion failed: {str(e)}")
        logger.debug("Stack trace:", exc_info=True)
        return False