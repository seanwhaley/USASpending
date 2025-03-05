"""Data processing functionality for converting and validating data."""
from typing import Dict, List, Any, Optional, Set, Callable
import csv
import json
import os
from pathlib import Path
import time
from concurrent.futures import ThreadPoolExecutor

from . import (
    get_logger, ConfigurationError, 
    create_components_from_config,
    EntityFactory, EntityStore, ValidationService,
    ensure_directory_exists as ensure_directory
)
from .interfaces import IDataProcessor
from .config import ConfigManager
from .entity_mapper import EntityMapper
from .file_utils import get_memory_efficient_reader, write_json_file

logger = get_logger(__name__)

class DataProcessor(IDataProcessor):
    """Processes data records according to configured rules."""
    
    def __init__(self, config: ConfigManager, entity_mapper: EntityMapper):
        """Initialize processor with configuration and mapper.
        
        Args:
            config: Configuration manager instance
            entity_mapper: Entity mapper instance for data transformation
        """
        self.config = config
        self.entity_mapper = entity_mapper
        self.stats: Dict[str, int] = {
            'processed_records': 0,
            'failed_records': 0,
            'skipped_records': 0,
            'entity_counts': {}
        }
        
    def process_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single data record.
        
        Args:
            record: Raw data record
            
        Returns:
            Processed record
        """
        try:
            self.stats['processed_records'] += 1
            result = self.entity_mapper.map_entity(record)
            if result and 'entity_type' in result:
                self.stats['entity_counts'][result['entity_type']] = \
                    self.stats['entity_counts'].get(result['entity_type'], 0) + 1
            return result
        except Exception as e:
            self.stats['failed_records'] += 1
            logger.error(f"Failed to process record: {str(e)}")
            return {}
            
    def process_batch(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process a batch of records.
        
        Args:
            records: List of raw data records
            
        Returns:
            List of processed records
        """
        return [
            processed for processed in (
                self.process_record(record) for record in records
            ) if processed
        ]
        
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get processing statistics.
        
        Returns:
            Dictionary of processing statistics
        """
        return self.stats.copy()

def convert_csv_to_json(config_manager: ConfigManager) -> bool:
    """Convert CSV data to JSON format using configuration.
    
    Args:
        config_manager: Configuration manager instance
        
    Returns:
        True if conversion successful, False otherwise
    """
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
        
        # Create entity mapper with correct config sections
        entity_mapper = EntityMapper({
            'entities': config.get('entities', {}),
            'field_properties': config.get('field_properties', {}),
            'adapters': config.get('adapters', {})
        })
        
        # Create processor instance
        processor = DataProcessor(config_manager, entity_mapper)
        
        # Create entity accumulator based on all defined entity types
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
                for batch in reader:
                    try:
                        # Process batch
                        processed = processor.process_batch(batch)
                        logger.info(f"Processed {len(batch)} records in batch.")
                        
                        # Group by entity type and accumulate
                        has_new_entities = False
                        for record in processed:
                            entity_type = record.get('entity_type')
                            if entity_type in processed_data:
                                processed_data[entity_type].append(record)
                                has_new_entities = True
                                logger.debug(f"Accumulated {entity_type} entity")
                        
                        # Increment batch count
                        batch_count += 1
                        
                        # Write all entities if threshold reached or any new entities added
                        if batch_count % write_threshold == 0 and has_new_entities:
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
                existing_data = {entity_type: []}
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