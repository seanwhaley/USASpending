"""Data processing module for converting and transforming data."""
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
import json
import csv

from .config import ConfigManager
from .logging_config import get_logger
from .file_utils import (
    ensure_directory,
    get_memory_efficient_reader,
    write_json_file
)
from .interfaces import IDataProcessor
from .entity_mapper import EntityMapper
from .exceptions import ProcessingError

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
            'skipped_records': 0
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
            return self.entity_mapper.map_entity(record)
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
        batch_size = config.get('processing', {}).get('batch_size', 1000)
        
        # Create entity mapper
        entity_types = config_manager.get_entity_types()
        processed_data: Dict[str, List[Dict[str, Any]]] = {
            entity_type: [] for entity_type in entity_types
        }
        
        # Process data in batches
        logger.info("Starting CSV to JSON conversion...")
        reader = get_memory_efficient_reader(
            str(input_path),
            batch_size=batch_size
        )
        
        for batch in reader:
            try:
                # Create processor for batch
                processor = DataProcessor(
                    config_manager,
                    EntityMapper(config.get('adapters', {}))
                )
                
                # Process batch
                processed = processor.process_batch(batch)
                
                # Group by entity type
                for record in processed:
                    entity_type = record.get('entity_type')
                    if entity_type in processed_data:
                        processed_data[entity_type].append(record)
                        
            except Exception as e:
                logger.error(f"Error processing batch: {str(e)}")
                continue
                
        # Write results
        for entity_type, entities in processed_data.items():
            if entities:
                output_file = output_dir / f"{entity_type}.json"
                write_json_file(
                    str(output_file),
                    {entity_type: entities},
                    make_dirs=True
                )
                logger.info(f"Wrote {len(entities)} {entity_type} records to {output_file}")
                
        return True
        
    except Exception as e:
        logger.error(f"Conversion failed: {str(e)}")
        logger.debug("Stack trace:", exc_info=True)
        return False