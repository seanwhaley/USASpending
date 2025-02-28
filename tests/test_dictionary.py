"""Tests for data dictionary processing functionality."""
import pytest
from typing import Dict, Any

from usaspending.dictionary import (
    parse_domain_values,
    split_cell_values,
    csv_to_json
)

def test_parse_domain_values():
    """Test parsing of domain values with different formats."""
    # Test key-value pairs
    assert parse_domain_values("A = Value A, B = Value B") == {
        "A": "Value A",
        "B": "Value B"
    }
    
    # Test single values without keys
    assert parse_domain_values("Value1, Value2") == {
        "Value1": None,
        "Value2": None
    }
    
    # Test mixed format
    assert parse_domain_values("A = Value A\nValue B\nC = Value C") == {
        "A": "Value A",
        "Value B": None,
        "C": "Value C"
    }
    
    # Test empty input
    assert parse_domain_values("") == {}
    assert parse_domain_values(None) == {}

def test_split_cell_values():
    """Test splitting cell values with different configurations."""
    # Basic splitting
    assert split_cell_values("a,b,c") == ["a", "b", "c"]
    
    # Newline splitting
    assert split_cell_values("a\nb\nc") == ["a", "b", "c"]
    
    # Mixed delimiters
    assert split_cell_values("a,b\nc,d") == ["a", "b", "c", "d"]
    
    # Preserve newlines
    config = {
        'data_dictionary': {
            'parsing': {
                'preserve_newlines_for': ['test value']
            }
        }
    }
    test_value = "line 1\nline 2\nline 3"
    assert split_cell_values(test_value, True, config) == ["line 1", "line 2", "line 3"]
    
    # Empty input
    assert split_cell_values("") == []
    assert split_cell_values(None) == []

@pytest.fixture
def mock_config() -> Dict[str, Any]:
    """Create a mock configuration for testing."""
    return {
        'global': {
            'encoding': 'utf-8',
            'datetime_format': '%Y-%m-%dT%H:%M:%S'
        },
        'data_dictionary': {
            'input': {
                'file': 'test_dictionary.csv'
            },
            'output': {
                'file': 'test_output.json',
                'indent': 2,
                'ensure_ascii': False
            },
            'parsing': {
                'preserve_newlines_for': ['Definition']
            }
        }
    }

def test_csv_to_json(tmp_path, mock_config, caplog):
    """Test full CSV to JSON conversion process."""
    # Create test CSV file
    csv_content = '''Element,Definition,FPDS Data Dictionary Element,Grouping,Domain Values,Domain Values Code Description
Test Element,Test Definition,FPDS Element,Test Group,A = Value A,A = Description A
'''
    csv_path = tmp_path / "test_dictionary.csv"
    csv_path.write_text(csv_content)
    
    # Update config with test paths
    mock_config['data_dictionary']['input']['file'] = str(csv_path)
    mock_config['data_dictionary']['output']['file'] = str(tmp_path / "test_output.json")
    
    # Run conversion
    result = csv_to_json(mock_config)
    assert result is True
    
    # Verify output file exists and contains expected content
    output_path = tmp_path / "test_output.json"
    assert output_path.exists()
    
    # Check JSON content
    import json
    with open(output_path) as f:
        data = json.load(f)
    
    assert "metadata" in data
    assert "elements" in data
    assert len(data["elements"]) == 1
    
    element = data["elements"][0]
    assert element["element_info"]["element"] == "Test Element"
    assert element["domain_info"]["values"] == {"A": "Value A"}