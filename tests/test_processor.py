"""Tests for data processing functionality."""
import pytest
import json
import os
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, mock_open
import csv

from usaspending.processor import DataProcessor, convert_csv_to_json, _write_entity_files
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
            },
            'processing': {'records_per_chunk': 100}
        },
        'processing': {'batch_size': 100},
        'adapters': {},
        'entities': {'test_entity': {}, 'contract': {}, 'agency': {}},
        'field_properties': {}
    }
    config.get_entity_types.return_value = ['test_entity', 'contract', 'agency']
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
    assert all(isinstance(v, int) for v in stats['entity_counts'].values())
    
    # Verify stats is a copy, not the original
    stats['processed_records'] = 999
    assert processor.stats['processed_records'] == 2

@pytest.mark.parametrize("entity_type", ["contract", "agency", None])
def test_process_record_different_entity_types(processor, mock_entity_mapper, entity_type):
    """Test processing records of different entity types."""
    # Configure mock to return different entity types
    if entity_type:
        mock_entity_mapper.map_entity.return_value = {
            'entity_type': entity_type,
            'id': '123'
        }
    else:
        mock_entity_mapper.map_entity.return_value = {}  # No entity type
    
    result = processor.process_record({'id': '1'})
    
    if entity_type:
        assert result['entity_type'] == entity_type
        assert processor.stats['entity_counts'].get(entity_type, 0) == 1
    else:
        assert result == {}

def test_process_batch_with_failures(processor, mock_entity_mapper):
    """Test batch processing with some failures."""
    # Configure mapper to succeed for first record, fail for second
    records = [{'id': '1'}, {'id': '2'}]
    
    def side_effect(record):
        if record['id'] == '1':
            return {'entity_type': 'test_entity', 'id': '1'}
        else:
            raise Exception("Processing failed for record 2")
            
    mock_entity_mapper.map_entity.side_effect = side_effect
    
    results = processor.process_batch(records)
    
    assert len(results) == 1  # Only one successful result
    assert results[0]['id'] == '1'
    assert processor.stats['processed_records'] == 2
    assert processor.stats['failed_records'] == 1

@patch('usaspending.processor.ensure_directory')
@patch('usaspending.processor.get_memory_efficient_reader')
@patch('usaspending.processor.EntityMapper')
@patch('usaspending.processor._write_entity_files')
def test_convert_csv_to_json_success(mock_write, mock_mapper_cls, mock_reader, mock_ensure_dir, mock_config):
    """Test successful CSV to JSON conversion."""
    # Setup mocks
    mock_input_path = MagicMock()
    mock_input_path.exists.return_value = True
    
    # Prepare batch data
    mock_batch_1 = [{'id': '1', 'name': 'Test 1'}]
    mock_batch_2 = [{'id': '2', 'name': 'Test 2'}]
    mock_reader.return_value.__enter__.return_value = [mock_batch_1, mock_batch_2]
    
    # Configure mapper to return entities with proper entity type
    mock_mapper = mock_mapper_cls.return_value
    mock_mapper.map_entity.side_effect = [
        {'entity_type': 'contract', 'id': '1'},
        {'entity_type': 'agency', 'id': '2'}
    ]
    
    # Run with patched Path object
    with patch('usaspending.processor.Path', return_value=mock_input_path):
        result = convert_csv_to_json(mock_config)
    
    # Assertions
    assert result is True
    mock_ensure_dir.assert_called_once()
    mock_write.assert_called()  # Should be called multiple times
    
    # Check that _write_entity_files was called at least twice (once for each batch)
    assert mock_write.call_count >= 2

@patch('usaspending.processor.Path')
def test_convert_csv_to_json_missing_file(mock_path, mock_config):
    """Test conversion with missing input file."""
    # Configure Path mock
    mock_input = MagicMock()
    mock_input.exists.return_value = False
    mock_path.return_value = mock_input
    
    result = convert_csv_to_json(mock_config)
    
    assert result is False

@patch('usaspending.processor.Path')
@patch('usaspending.processor.get_memory_efficient_reader')
@patch('usaspending.processor.EntityMapper')
@patch('usaspending.processor._write_entity_files')
def test_convert_csv_keyboard_interrupt(mock_write, mock_mapper, mock_reader, mock_path, mock_config):
    """Test handling of KeyboardInterrupt during conversion."""
    # Configure Path mock
    mock_input = MagicMock()
    mock_input.exists.return_value = True
    mock_path.return_value = mock_input
    
    # Configure reader to raise KeyboardInterrupt after first batch
    mock_reader.return_value.__enter__.return_value = [[{'id': '1'}]]
    mock_reader.return_value.__enter__.side_effect = KeyboardInterrupt()
    
    # Run with exception handling
    with pytest.raises(KeyboardInterrupt):
        convert_csv_to_json(mock_config)
    
    # Should still try to write accumulated data
    mock_write.assert_called()

@patch('usaspending.processor.Path')
@patch('usaspending.processor.get_memory_efficient_reader')
@patch('usaspending.processor.EntityMapper')
@patch('usaspending.processor._write_entity_files')
def test_convert_csv_batch_exception(mock_write, mock_mapper, mock_reader, mock_path, mock_config):
    """Test handling of exceptions during batch processing."""
    # Configure Path mock
    mock_input = MagicMock()
    mock_input.exists.return_value = True
    mock_path.return_value = mock_input
    
    # Configure reader to return batches
    mock_reader.return_value.__enter__.return_value = [
        [{'id': '1'}],  # First batch succeeds
        [{'id': '2'}]   # Second batch will fail
    ]
    
    # Configure mapper to raise exception for second record
    def side_effect(record):
        if record['id'] == '1':
            return {'entity_type': 'contract', 'id': '1'}
        else:
            raise Exception("Test exception")
            
    mock_mapper.return_value.map_entity.side_effect = side_effect
    
    # Run conversion
    result = convert_csv_to_json(mock_config)
    
    # Should continue despite batch exception
    assert result is True
    mock_write.assert_called()  # Should still write successful batches

@patch('usaspending.processor.Path')
@patch('usaspending.processor.write_json_file')
def test_write_entity_files_new(mock_write_json, mock_path, tmp_path):
    """Test writing entity files with new files."""
    # Setup
    output_dir = MagicMock()
    mock_path.return_value = output_dir
    
    # Data to write
    entity_data = {
        'contract': [{'id': '1'}, {'id': '2'}],
        'agency': [{'id': 'A1'}]
    }
    
    # Run function
    _write_entity_files(entity_data, tmp_path, 'w')
    
    # Verify
    assert mock_write_json.call_count == 2  # One call per entity type
    
    # Check first call arguments
    args, kwargs = mock_write_json.call_args_list[0]
    assert kwargs['make_dirs'] is True
    # Assuming first or second call is for contract entity
    data_arg = None
    for call in mock_write_json.call_args_list:
        if 'contract' in str(call):
            data_arg = call[0][1]
            break
    assert data_arg is not None
    assert data_arg['contract'] == [{'id': '1'}, {'id': '2'}]

@patch('usaspending.processor.Path')
@patch('usaspending.processor.open', new_callable=mock_open, read_data='{"contract": [{"id": "0"}]}')
@patch('usaspending.processor.write_json_file')
@patch('builtins.json.load')
def test_write_entity_files_append(mock_json_load, mock_write_json, mock_open_file, mock_path):
    """Test writing entity files in append mode."""
    # Setup
    output_dir = MagicMock()
    output_file = MagicMock()
    output_file.exists.return_value = True
    mock_path.return_value = output_dir
    output_dir.__truediv__.return_value = output_file
    
    # Configure mock to return existing data when json.load is called
    mock_json_load.return_value = {'contract': [{'id': '0'}]}
    
    # Data to write
    entity_data = {
        'contract': [{'id': '1'}, {'id': '2'}]
    }
    
    # Run function
    _write_entity_files(entity_data, Path('dummy'), 'a')
    
    # Verify file was opened for reading
    mock_open_file.assert_called_with(output_file, 'r')
    
    # Verify write_json_file was called with combined data
    mock_write_json.assert_called_once()
    args, kwargs = mock_write_json.call_args
    assert kwargs['make_dirs'] is True
    assert len(args[1]['contract']) == 3  # Combined 1 existing + 2 new

@patch('usaspending.processor.Path')
@patch('usaspending.processor.open', side_effect=json.JSONDecodeError("Test error", "", 0))
@patch('usaspending.processor.write_json_file')
def test_write_entity_files_json_error(mock_write_json, mock_open_file, mock_path):
    """Test handling JSONDecodeError when reading existing file."""
    # Setup
    output_dir = MagicMock()
    output_file = MagicMock()
    output_file.exists.return_value = True
    mock_path.return_value = output_dir
    output_dir.__truediv__.return_value = output_file
    
    # Data to write
    entity_data = {
        'contract': [{'id': '1'}]
    }
    
    # Run function - should handle the error gracefully
    _write_entity_files(entity_data, Path('dummy'), 'a')
    
    # Verify write_json_file was still called with just the new data
    mock_write_json.assert_called_once()
    args, kwargs = mock_write_json.call_args
    assert args[1]['contract'] == [{'id': '1'}]

@patch('usaspending.processor.Path')
@patch('usaspending.processor.write_json_file', side_effect=Exception("Write failed"))
def test_write_entity_files_exception(mock_write_json, mock_path):
    """Test exception handling when writing files."""
    # Setup
    output_dir = MagicMock()
    mock_path.return_value = output_dir
    
    # Data to write
    entity_data = {'contract': [{'id': '1'}]}
    
    # Run function - should propagate the error
    with pytest.raises(Exception) as exc:
        _write_entity_files(entity_data, Path('dummy'), 'w')
    
    assert "Write failed" in str(exc.value)

@pytest.mark.integration
@patch('usaspending.processor.Path')
@patch('usaspending.processor.ensure_directory')
@patch('usaspending.processor.get_memory_efficient_reader')
@patch('usaspending.processor._write_entity_files')
def test_convert_csv_to_json_full_cycle(mock_write, mock_reader, mock_ensure_dir, mock_path, mock_config):
    """Integration test for full conversion cycle with threshold writing."""
    # Setup Path mocks
    mock_input = MagicMock()
    mock_input.exists.return_value = True
    mock_output = MagicMock()
    
    mock_path.side_effect = [mock_input, mock_output]  # First call for input, second for output
    
    # Create 15 small batches to test threshold writing (threshold is 10)
    batches = [[{'id': f'{i}'}] for i in range(15)]
    mock_reader.return_value.__enter__.return_value = batches
    
    # Configure the config to make sure we test the write_threshold logic
    mock_config.get_config.return_value['system']['processing']['records_per_chunk'] = 1
    
    # Run conversion
    result = convert_csv_to_json(mock_config)
    
    # Should succeed
    assert result is True
    
    # Should have called write_entity_files at least 3 times:
    # 1. At batch 10 (threshold)
    # 2. At batch 20 (threshold) - we only have 15 batches though
    # 3. Final write for remaining data
    assert mock_write.call_count >= 2

@patch('usaspending.processor.Path')
@patch('usaspending.processor.ensure_directory')
@patch('usaspending.processor.get_memory_efficient_reader')
@patch('usaspending.processor.EntityMapper')
@patch('usaspending.processor._write_entity_files')
def test_convert_csv_to_json_entity_filtering(mock_write, mock_mapper_cls, mock_reader, mock_ensure_dir, mock_path, mock_config):
    """Test filtering entities by type during conversion."""
    # Setup Path mocks
    mock_input = MagicMock()
    mock_input.exists.return_value = True
    mock_output = MagicMock()
    mock_path.side_effect = [mock_input, mock_output]
    
    # Configure reader to return one batch
    mock_batch = [
        {'id': '1', 'type': 'contract'},
        {'id': '2', 'type': 'agency'},
        {'id': '3', 'type': 'unknown'}
    ]
    mock_reader.return_value.__enter__.return_value = [mock_batch]
    
    # Configure mapper to return correct entity types
    def map_entity_side_effect(record):
        entity_type = record.get('type')
        if entity_type in ['contract', 'agency']:
            return {'entity_type': entity_type, 'id': record['id']}
        return {}
        
    mock_mapper = mock_mapper_cls.return_value
    mock_mapper.map_entity.side_effect = map_entity_side_effect
    
    # Run conversion
    result = convert_csv_to_json(mock_config)
    
    # Should succeed
    assert result is True
    
    # Should only accumulate contract and agency entities
    # Find the call data for _write_entity_files
    for call in mock_write.call_args_list:
        args, _ = call
        data = args[0]
        assert len(data.get('contract', [])) <= 1  # Should have 0 or 1 contract
        assert len(data.get('agency', [])) <= 1  # Should have 0 or 1 agency
        assert 'unknown' not in data  # Should not have unknown entity type