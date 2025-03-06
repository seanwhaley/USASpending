"""Tests for data processing functionality."""
import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

from usaspending.processor import DataProcessor, convert_csv_to_json
from usaspending.entity_mapper import EntityMapper
from usaspending.config import ConfigManager
from usaspending.exceptions import ProcessingError

@pytest.fixture
def mock_config():
    """Create mock configuration manager."""
    config = Mock(spec=ConfigManager)
    config.get_config.return_value = {
        'system': {
            'io': {
                'input': {'file': 'test.csv'},
                'output': {'directory': 'output'}
            }
        },
        'processing': {'batch_size': 100},
        'adapters': {},
        'entities': {'test_entity': {}}
    }
    config.get_entity_types.return_value = ['test_entity']
    return config

@pytest.fixture
def mock_entity_mapper():
    """Create mock entity mapper."""
    mapper = Mock(spec=EntityMapper)
    mapper.map_entity.return_value = {
        'entity_type': 'test_entity',
        'id': '123',
        'name': 'Test Entity'
    }
    return mapper

@pytest.fixture
def processor(mock_config, mock_entity_mapper):
    """Create processor instance with mocked dependencies."""
    return DataProcessor(mock_config, mock_entity_mapper)

def test_process_record_success(processor, mock_entity_mapper):
    """Test successful record processing."""
    record = {'id': '123', 'name': 'Test'}
    result = processor.process_record(record)
    
    assert result == mock_entity_mapper.map_entity.return_value
    mock_entity_mapper.map_entity.assert_called_once_with(record)
    assert processor.stats['processed_records'] == 1
    assert processor.stats['failed_records'] == 0

def test_process_record_failure(processor, mock_entity_mapper):
    """Test record processing failure."""
    mock_entity_mapper.map_entity.side_effect = Exception("Mapping failed")
    
    result = processor.process_record({'id': 'bad'})
    
    assert result == {}
    assert processor.stats['processed_records'] == 1
    assert processor.stats['failed_records'] == 1

def test_process_batch(processor):
    """Test batch processing."""
    records = [
        {'id': '1', 'name': 'First'},
        {'id': '2', 'name': 'Second'}
    ]
    
    results = processor.process_batch(records)
    
    assert len(results) == 2
    assert all(r['entity_type'] == 'test_entity' for r in results)
    assert processor.stats['processed_records'] == 2

def test_get_processing_stats(processor):
    """Test getting processing statistics."""
    # Process some records to generate stats
    processor.process_record({'id': '1'})
    processor.process_record({'id': '2'})
    
    stats = processor.get_processing_stats()
    
    assert stats['processed_records'] == 2
    assert isinstance(stats, dict)
    assert all(isinstance(v, int) for v in stats.values())

@pytest.mark.integration
def test_convert_csv_to_json(mock_config, tmp_path):
    """Integration test for CSV to JSON conversion."""
    # Setup test paths
    input_file = tmp_path / "test.csv"
    output_dir = tmp_path / "output"
    
    # Create test CSV
    input_file.write_text(
        "id,name,type\\n"
        "1,Test Entity,test_entity\\n"
        "2,Another Entity,test_entity"
    )
    
    # Update config mock
    mock_config.get_config.return_value.update({
        'system': {
            'io': {
                'input': {'file': str(input_file)},
                'output': {'directory': str(output_dir)}
            }
        }
    })
    
    # Run conversion
    result = convert_csv_to_json(mock_config)
    
    assert result is True
    assert output_dir.exists()
    assert (output_dir / "test_entity.json").exists()

@pytest.mark.parametrize("missing_file", [True, False])
def test_convert_csv_to_json_error_handling(mock_config, tmp_path, missing_file):
    """Test error handling in CSV to JSON conversion."""
    input_file = tmp_path / "missing.csv" if missing_file else tmp_path / "test.csv"
    if not missing_file:
        input_file.write_text("id,name\\n1,Test\\n")
    
    mock_config.get_config.return_value.update({
        'system': {
            'io': {
                'input': {'file': str(input_file)},
                'output': {'directory': str(tmp_path)}
            }
        }
    })
    
    result = convert_csv_to_json(mock_config)
    assert result is False if missing_file else True