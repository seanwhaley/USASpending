"""Benchmark script for validation performance testing."""
import sys
import os
import time
import csv
import json
import logging
from pathlib import Path
from typing import Dict, Any, List

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.usaspending.config import load_config, setup_logging
from src.usaspending.validation import ValidationEngine, ValidationResult
from src.usaspending.entity_factory import EntityFactory

def run_validation_benchmark(csv_path: str, config_path: str, num_records: int = 100) -> Dict[str, Any]:
    """
    Run validation benchmark on a sample of records.
    
    Args:
        csv_path: Path to the CSV file to process
        config_path: Path to the configuration file
        num_records: Number of records to process
        
    Returns:
        Dictionary with benchmark results
    """
    start_time = time.time()
    
    # Load configuration
    config = load_config(config_path)
    
    # Setup logging
    logger = setup_logging()
    logger.setLevel(logging.INFO)
    
    # Initialize validation engine
    validator = ValidationEngine(config)
    
    # Create entity stores for validation
    entity_stores = {
        'recipient': EntityFactory.create_store('recipient', 'output/entities', config),
        'agency': EntityFactory.create_store('agency', 'output/entities', config),
        'contract': EntityFactory.create_store('contract', 'output/entities', config),
        'transaction': EntityFactory.create_store('transaction', 'output/entities', config)
    }
    
    # Process records
    results = {
        'total_records': 0,
        'valid_records': 0,
        'invalid_records': 0,
        'validation_time': 0,
        'errors_by_entity': {},
        'errors_by_field': {},
        'errors_by_type': {}
    }
    
    # Read CSV file
    with open(csv_path, 'r', encoding=config['global']['encoding']) as csvfile:
        reader = csv.DictReader(csvfile)
        
        for i, record in enumerate(reader):
            if i >= num_records:
                break
                
            results['total_records'] += 1
            record_valid = True
            
            # Process each entity type
            for entity_type, store in entity_stores.items():
                # Extract entity data
                entity_data = store.extract_entity_data(record)
                if entity_data:
                    # Validate entity
                    validation_start = time.time()
                    validation_results = validator.validate_entity(entity_type, entity_data, context=record)
                    validation_time = time.time() - validation_start
                    results['validation_time'] += validation_time
                    
                    # Check for invalid results
                    invalid_results = [r for r in validation_results if not r.valid]
                    if invalid_results:
                        record_valid = False
                        
                        # Track errors by entity
                        if entity_type not in results['errors_by_entity']:
                            results['errors_by_entity'][entity_type] = 0
                        results['errors_by_entity'][entity_type] += 1
                        
                        # Track errors by field and type
                        for result in invalid_results:
                            field_name = result.field_name if result.field_name else 'unknown'
                            if field_name not in results['errors_by_field']:
                                results['errors_by_field'][field_name] = 0
                            results['errors_by_field'][field_name] += 1
                            
                            error_type = result.error_type if result.error_type else 'unknown'
                            if error_type not in results['errors_by_type']:
                                results['errors_by_type'][error_type] = 0
                            results['errors_by_type'][error_type] += 1
            
            # Update valid/invalid counts
            if record_valid:
                results['valid_records'] += 1
            else:
                results['invalid_records'] += 1
    
    # Calculate timing metrics
    total_time = time.time() - start_time
    results['total_time'] = total_time
    results['records_per_second'] = results['total_records'] / total_time if total_time > 0 else 0
    results['validation_time_per_record'] = results['validation_time'] / results['total_records'] if results['total_records'] > 0 else 0
    
    return results

def print_benchmark_results(results: Dict[str, Any]) -> None:
    """Print benchmark results in a readable format."""
    print("\n===== Validation Benchmark Results =====")
    print(f"Total records processed: {results['total_records']}")
    print(f"Valid records: {results['valid_records']} ({results['valid_records'] / results['total_records'] * 100:.1f}%)")
    print(f"Invalid records: {results['invalid_records']} ({results['invalid_records'] / results['total_records'] * 100:.1f}%)")
    print(f"Total processing time: {results['total_time']:.2f}s")
    print(f"Processing rate: {results['records_per_second']:.2f} records/s")
    print(f"Average validation time: {results['validation_time_per_record'] * 1000:.2f}ms per record")
    
    if results['errors_by_entity']:
        print("\nErrors by entity type:")
        for entity, count in sorted(results['errors_by_entity'].items(), key=lambda x: x[1], reverse=True):
            print(f"  {entity}: {count} errors")
    
    if results['errors_by_field']:
        print("\nTop 10 fields with validation errors:")
        field_errors = sorted(results['errors_by_field'].items(), key=lambda x: x[1], reverse=True)
        for field, count in field_errors[:10]:
            print(f"  {field}: {count} errors")
    
    if results['errors_by_type']:
        print("\nErrors by type:")
        for error_type, count in sorted(results['errors_by_type'].items(), key=lambda x: x[1], reverse=True):
            print(f"  {error_type}: {count} errors")

def save_benchmark_results(results: Dict[str, Any], output_path: str) -> None:
    """Save benchmark results to a JSON file."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    print(f"\nDetailed results saved to {output_path}")

if __name__ == "__main__":
    # Default values
    csv_path = os.path.join(project_root, "FY2024_015_Contracts_Full_20250109_1.csv")
    config_path = os.path.join(project_root, "conversion_config.yaml")
    num_records = 100
    output_path = os.path.join(project_root, "validation_benchmark_results.json")
    
    # Override with command-line arguments if provided
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    if len(sys.argv) > 2:
        config_path = sys.argv[2]
    if len(sys.argv) > 3:
        num_records = int(sys.argv[3])
    if len(sys.argv) > 4:
        output_path = sys.argv[4]
    
    print(f"Running validation benchmark on {num_records} records from {csv_path}")
    print(f"Using configuration from {config_path}")
    
    # Run benchmark
    results = run_validation_benchmark(csv_path, config_path, num_records)
    
    # Print and save results
    print_benchmark_results(results)
    save_benchmark_results(results, output_path)