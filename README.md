# USASpending Data Processing Project

This project processes and transforms federal contract spending data from USASpending.gov into structured JSON format and prepares it for loading into a Neo4j graph database.

## Overview

The project consists of two main components:
1. Data Dictionary Processor - Converts the USASpending Data Dictionary into a structured JSON format
2. Contracts Data Processor - Processes federal contract transaction data into chunked JSON files with separated entity data

## Data Sources

### USASpending Data Dictionary
The data dictionary (`USASpending_Data_Dictionary_Crosswalk.csv`) provides metadata about all fields in USASpending datasets, including:
- Field definitions
- FPDS (Federal Procurement Data System) mappings
- Domain values and code descriptions
- File and element mappings

### Contracts Data
The contracts data (`FY2024_015_Contracts_Full_20250109_1.csv`) contains federal contract transactions with information about:
- Contract awards and modifications
- Financial details
- Agencies and recipients
- Locations and performance details

## Project Structure

```
├── conversion_config.yaml         # Configuration for both conversion processes
├── Data_Dictionary_CSV_to_JSON.py # Data Dictionary conversion script
├── Contracts_Full_CSV_to_JSON.py # Contracts data conversion script
├── create_neo4j_schema.cypher    # Neo4j database schema definition
└── load_neo4j_data.py           # (Future) Script to load data into Neo4j
```

## Configuration

The project uses a YAML configuration file (`conversion_config.yaml`) that controls:

1. Global Settings:
   - Character encoding
   - Date/time formats

2. Data Dictionary Settings:
   - Input/output file paths
   - Required columns
   - Parsing rules for special fields

3. Contracts Processing Settings:
   - Chunking configuration
   - Entity separation rules
   - Field categorization
   - Type conversion rules

## Processing Pipeline

### 1. Data Dictionary Processing
The Data Dictionary converter:
- Reads the CSV data dictionary
- Parses domain values and code descriptions
- Structures field definitions and mappings
- Outputs a JSON file used by the contracts processor

### 2. Contracts Data Processing
The Contracts processor:

a. **Entity Separation**
   - Extracts recipient details
   - Separates agency information
   - Identifies location data
   - Creates reference IDs for entities

b. **Data Chunking**
   - Splits large datasets into manageable chunks
   - Creates an index file for chunk management
   - Maintains consistent JSON structure across chunks

c. **Data Type Conversion**
   - Converts dates to ISO format
   - Handles numeric fields
   - Processes boolean values
   - Maintains domain value mappings

### 3. Neo4j Integration

The project includes a Neo4j schema that defines:

1. **Node Types**:
   - Transaction
   - Award
   - Agency
   - Recipient
   - Location
   - FinancialInfo

2. **Relationships**:
   - MODIFIES (Transaction → Award)
   - AWARDED_BY (Award → Agency)
   - AWARDED_TO (Award → Recipient)
   - LOCATED_AT (Recipient/Agency → Location)
   - HAS_FINANCIAL_INFO (Transaction → FinancialInfo)

## Output Structure

The processing creates several JSON files:

1. **Entity Files**:
   - `*_recipient.json`: Recipient details
   - `*_agency.json`: Agency information
   - `*_location.json`: Location data

2. **Transaction Chunks**:
   - `*_part{n}.json`: Chunked transaction data
   - Each chunk contains metadata and transaction records

3. **Index File**:
   - `*_index.json`: Metadata about all chunks
   - Record counts and file references

## Usage

1. **Set Up Configuration**:
   ```yaml
   global:
     encoding: utf-8-sig
     date_format: "%Y-%m-%d"
   ```

2. **Process Data Dictionary**:
   ```bash
   python Data_Dictionary_CSV_to_JSON.py
   ```

3. **Process Contracts Data**:
   ```bash
   python Contracts_Full_CSV_to_JSON.py
   ```

## Dependencies

- Python 3.x
- PyYAML
- Neo4j Database (for loading data)

## Future Enhancements

- Implementation of Neo4j data loader
- Data validation and error reporting
- Performance optimization for larger datasets
- API integration for direct USASpending.gov data access

## Contributing

When contributing to this project:
1. Use the configuration file for any new settings
2. Follow the existing code structure for new features
3. Update documentation for significant changes
4. Add appropriate error handling and logging

# USASpending CSV to JSON Conversion Process

## Overview
The conversion process handles large federal contracting datasets, transforming them from CSV format into structured JSON with entity separation and relationship tracking.

## Process Flow

### 1. Configuration and Setup
- Loads YAML configuration from `conversion_config.yaml`
- Validates required configuration sections and parameters
- Sets up logging with both console and file handlers
- Initializes error tracking and statistics

### 2. Entity Management (EntityStore Class)
The EntityStore class manages repeated entities:

#### Entity Types:
- Recipients (with parent-child relationships)
- Agencies (hierarchical: agency → sub-agency → office)
- Locations (with address components)
- Awards

#### Entity Processing:
- Generates consistent entity keys using key fields
- Maintains relationships between entities
- Handles hierarchical and transactional relationships
- Caches entities to prevent duplication
- Tracks statistics (total references, unique entities)

#### Data Structure:
```json
{
    "metadata": {
        "entity_type": "...",
        "total_references": 0,
        "unique_entities": 0,
        "relationship_counts": {},
        "generated_date": "..."
    },
    "entities": {},
    "relationships": {}
}
```

### 3. Data Chunking
- Processes CSV in batches for memory efficiency
- Creates separate files for different entity types
- Maintains index file for chunk management

### 4. Type Conversion and Validation
- Converts dates to ISO format
- Handles numeric fields
- Processes boolean values
- Validates data against configuration rules

## Output Files
1. Entity Files:
   - `*_recipient.json`: Recipient details with hierarchical structure
   - `*_agency.json`: Agency information with office relationships
   - `*_location.json`: Location data with consistent IDs

2. Transaction Files:
   - `*_part{n}.json`: Chunked transaction records
   - Each chunk includes metadata and batch of records

## Error Handling
- Detailed logging at multiple levels (INFO, DEBUG)
- Exception handling with custom error messages
- Transaction validation and error tracking
- Optional skip of invalid records based on configuration

## Best Practices
1. Memory Management:
   - Batch processing of CSV records
   - Entity caching with controlled growth
   - Regular buffer flushing

2. Data Integrity:
   - Consistent key generation
   - Relationship validation
   - Data type enforcement

3. Performance:
   - Efficient caching of repeated entities
   - Optimized relationship tracking
   - Controlled file I/O with buffering