"""Data dictionary processing module.

This module handles the conversion of the USASpending Data Dictionary
from CSV format to a structured JSON format.
"""
import csv
import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional

def validate_domain_value_format(value: str, field_name: str) -> None:
    """Validate domain value format is correct at initialization."""
    if not value:
        return
        
    lines = [line.strip() for line in value.replace(',', '\n').split('\n')]
    for line in lines:
        if '=' in line:
            parts = [p.strip() for p in line.split('=', 1)]
            if len(parts) != 2 or not parts[0] or not parts[1]:
                raise ValueError(f"Invalid domain value format in {field_name}: {line}")
        elif not line.strip():
            raise ValueError(f"Empty domain value in {field_name}")

def parse_domain_values(value: str) -> Dict[str, Optional[str]]:
    """Parse domain values that may contain key-value pairs.
    
    Args:
        value: Raw domain value string from CSV
        
    Returns:
        Dictionary of parsed key-value pairs or values
    """
    if not value or not value.strip():
        return {}
    
    result = {}
    # Remove any leading/trailing whitespace first
    value = value.strip()
    
    # Handle both comma-separated and newline-separated values
    lines = []
    for line in value.split('\n'):
        lines.extend(part.strip() for part in line.split(','))
    
    # Filter out empty lines before processing
    lines = [line for line in lines if line]
    
    for line in lines:
        if '=' in line:
            parts = line.split('=', 1)
            key = parts[0].strip()
            val = parts[1].strip() if len(parts) > 1 else None
            if key:  # Only add if key is not empty
                result[key] = val
        elif line.strip():
            result[line.strip()] = None
    
    return result

def validate_dictionary_mappings(config: Dict[str, Any]) -> None:
    """Validate dictionary field mappings at initialization time."""
    if not isinstance(config, dict):
        raise ValueError("Configuration must be a dictionary")
    
    # Validate global config exists and has required fields
    if 'global' not in config:
        raise ValueError("Global configuration is missing")
    if 'encoding' not in config['global']:
        raise ValueError("Global encoding configuration is missing")
    if 'datetime_format' not in config['global']:
        raise ValueError("Global datetime format configuration is missing")
        
    dict_config = config.get('data_dictionary')
    if not isinstance(dict_config, dict):
        raise ValueError("Data dictionary config must be a dictionary")

    # Validate input configuration
    input_cfg = dict_config.get('input', {})
    if not isinstance(input_cfg, dict):
        raise ValueError("Input configuration must be a dictionary")
    
    if 'file' not in input_cfg:
        raise ValueError("Input file path must be specified")
        
    required = {'Element', 'Definition', 'Domain Values', 'Domain Values Code Description'}
    configured = set(input_cfg.get('required_columns', []))
    missing = required - configured
    if missing:
        raise ValueError(f"Missing required column configuration: {', '.join(missing)}")

    # Validate output configuration
    output_cfg = dict_config.get('output', {})
    if not isinstance(output_cfg, dict):
        raise ValueError("Output configuration must be a dictionary")
    
    if 'file' not in output_cfg:
        raise ValueError("Output file path must be specified")

    # Validate parsing configuration
    parsing = dict_config.get('parsing', {})
    if not isinstance(parsing, dict):
        raise ValueError("Parsing configuration must be a dictionary")
        
    preserve_newlines = parsing.get('preserve_newlines_for', [])
    if not isinstance(preserve_newlines, list):
        raise ValueError("preserve_newlines_for must be a list")
    
    # Validate preserve_newlines entries against known column names
    valid_columns = {
        'Element', 'Definition', 'Domain Values', 'Domain Values Code Description',
        'Award File', 'Award Element', 
        'Subaward File', 'Subaward Element',
        'Account File', 'Account Element',
        'FPDS Data Dictionary Element', 'Grouping'
    }
    invalid_columns = set(preserve_newlines) - valid_columns
    if invalid_columns:
        raise ValueError(f"Invalid columns in preserve_newlines_for: {', '.join(invalid_columns)}")

    # Validate field references are valid
    file_mappings = {'Award', 'Subaward', 'Account'}
    field_types = {'File', 'Element'}
    for mapping in file_mappings:
        for field in field_types:
            col_name = f"{mapping} {field}"
            if col_name not in configured:
                raise ValueError(f"Missing mapping configuration for {col_name}")

def split_cell_values(value: str, preserve_newlines: bool = False, 
                     config: Optional[Dict[str, Any]] = None) -> List[str]:
    """Split cell values according to configuration.
    
    Args:
        value: Raw cell value to split
        preserve_newlines: Whether to preserve newlines in splitting
        config: DEPRECATED - no longer used
    """
    if not value or not value.strip():
        return []

    if preserve_newlines:
        values = [v.strip() for v in value.split('\n')]
    else:
        values = []
        for line in value.split('\n'):
            values.extend(v.strip() for v in line.split(','))

    seen = set()
    return [v for v in values if v.strip() and not (v in seen or seen.add(v))]

def csv_to_json(config: Dict[str, Any]) -> bool:
    """Convert data dictionary CSV to JSON using configuration settings.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        True if conversion was successful, False otherwise
    """
    try:
        # Validate all configuration first
        validate_dictionary_mappings(config)
        dict_config = config['data_dictionary']
        global_config = config['global']
        
        csv_file_path = os.path.abspath(dict_config['input']['file'])
        json_file_path = os.path.abspath(dict_config['output']['file'])
        
        # Validate file paths
        if not os.path.exists(csv_file_path):
            raise FileNotFoundError(f"Input CSV file not found: {csv_file_path}")
            
        # Create output directory if needed
        output_dir = os.path.dirname(json_file_path)
        if output_dir and not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except OSError as e:
                raise OSError(f"Failed to create output directory: {str(e)}")
        
        preserve_newlines_for = set(dict_config.get('parsing', {}).get('preserve_newlines_for', []))
        
        # Process CSV with validated configuration
        entries = []
        with open(csv_file_path, 'r', encoding=global_config['encoding']) as csvfile:
            reader = csv.DictReader(csvfile)
            
            # Pre-validate domain values format
            for row in reader:
                if not any(row.values()):
                    continue
                    
                # Validate domain value formats
                for field in ['Domain Values', 'Domain Values Code Description']:
                    if row.get(field):
                        validate_domain_value_format(row[field], field)
                        
                entry = {
                    "element_info": {
                        "element": row.get('Element', '').strip(),
                        "definition": row.get('Definition', '').strip(),
                        "fpds_element": row.get('FPDS Data Dictionary Element', '').strip(),
                        "grouping": row.get('Grouping', '').strip()
                    },
                    "domain_info": {
                        "values": parse_domain_values(row.get('Domain Values', '')),
                        "code_description": parse_domain_values(row.get('Domain Values Code Description', ''))
                    },
                    "file_mappings": {
                        "award": {
                            "file": split_cell_values(row.get('Award File', ''), 'Award File' in preserve_newlines_for),
                            "element": split_cell_values(row.get('Award Element', ''), 'Award Element' in preserve_newlines_for)
                        },
                        "subaward": {
                            "file": split_cell_values(row.get('Subaward File', ''), 'Subaward File' in preserve_newlines_for),
                            "element": split_cell_values(row.get('Subaward Element', ''), 'Subaward Element' in preserve_newlines_for)
                        },
                        "account": {
                            "file": split_cell_values(row.get('Account File', ''), 'Account File' in preserve_newlines_for),
                            "element": split_cell_values(row.get('Account Element', ''), 'Account Element' in preserve_newlines_for)
                        }
                    }
                }
                
                # Clean up empty values
                clean_entry = {}
                for category, data in entry.items():
                    if isinstance(data, dict):
                        clean_data = {k: v for k, v in data.items() if v not in (None, '', [], {})}
                        if clean_data:
                            clean_entry[category] = clean_data
                    elif data not in (None, '', [], {}):
                        clean_entry[category] = data
                
                if clean_entry:
                    entries.append(clean_entry)

        output = {
            "metadata": {
                "source": "USASpending Data Dictionary Crosswalk",
                "version": "1.0",
                "record_count": len(entries),
                "generated_at": datetime.now().strftime(global_config['datetime_format'])
            },
            "elements": entries
        }
        
        # Write to JSON file using validated configuration
        with open(json_file_path, 'w', encoding=global_config['encoding']) as jsonfile:
            json.dump(output, jsonfile, 
                     indent=dict_config['output'].get('indent', 2),
                     ensure_ascii=dict_config['output'].get('ensure_ascii', False))
        
        return True
        
    except Exception as e:
        print(f"Error processing data dictionary: {str(e)}")
        return False