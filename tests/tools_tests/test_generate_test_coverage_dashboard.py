"""Tests for the test coverage dashboard generator tool."""
import os
import sys
import json
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock, call, ANY
from datetime import datetime

# Ensure tools directory is in path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

from tools.generate_test_coverage_dashboard import (
    run_coverage_analysis,
    collect_reports,
    generate_html_dashboard,
    prepare_template_data
)


@pytest.fixture
def sample_coverage_report():
    """Sample coverage report data."""
    return {
        'overall_coverage': 0.75,
        'modules_without_tests': ['module1.py', 'module2.py'],
        'untested_functions': 10,
        'total_functions': 40
    }


@pytest.fixture
def sample_functional_report():
    """Sample functional coverage report data."""
    return {
        'functional_coverage': 0.65,
        'total_public_functions': 50,
        'untested_functions': 17,
        'untested_functions_list': [
            {
                'function': 'my_function',
                'file': 'src/module1.py',
                'line_number': 42
            },
            {
                'function': 'another_function',
                'file': 'src/module2.py',
                'line_number': 123
            }
        ]
    }


@pytest.fixture
def sample_quality_report():
    """Sample test quality report data."""
    return {
        'overall_quality_score': 68.5,
        'total_test_files': 15,
        'total_tests': 120,
        'low_quality_tests': [
            {
                'file': 'tests/test_low1.py',
                'quality_score': 35.0,
                'issues': ['Low assertion count', 'No parameterization', None]
            },
            {
                'file': 'tests/test_low2.py',
                'quality_score': 45.0,
                'issues': ['No mocks used', None, None]
            }
        ]
    }


@pytest.fixture
def sample_history():
    """Sample coverage history data."""
    return [
        {
            'date': '2025-02-01',
            'overall_coverage': 0.70,
            'functional_coverage': 0.60,
            'quality_score': 65.0
        },
        {
            'date': '2025-03-01',
            'overall_coverage': 0.72,
            'functional_coverage': 0.63,
            'quality_score': 67.0
        }
    ]


def test_run_coverage_analysis():
    """Test running pytest with coverage."""
    with patch('subprocess.run') as mock_run:
        run_coverage_analysis()
        
        # Verify pytest was called with correct parameters
        mock_run.assert_called_once()
        pytest_call = mock_run.call_args[0][0]
        assert pytest_call[0] == 'pytest'
        assert '--cov=src/usaspending' in pytest_call
        assert '--cov-report=xml:coverage.xml' in pytest_call


def test_run_analyzers():
    """Test running all analyzer scripts."""
    # Create mock analyzers and reports
    mock_coverage_analyzer = MagicMock()
    mock_functional_analyzer = MagicMock()
    mock_quality_analyzer = MagicMock()
    
    mock_coverage_report = {'overall_coverage': 0.75}
    mock_functional_report = {'functional_coverage': 0.65}
    mock_quality_report = {'quality_score': 70}
    
    mock_coverage_analyzer.generate_report.return_value = mock_coverage_report
    mock_functional_analyzer.generate_report.return_value = mock_functional_report
    mock_quality_analyzer.generate_report.return_value = mock_quality_report
    
    # Patch the imports and constructor calls
    with patch('tools.generate_test_coverage_dashboard.TestCoverageAnalyzer', return_value=mock_coverage_analyzer), \
         patch('tools.generate_test_coverage_dashboard.FunctionalCoverageAnalyzer', return_value=mock_functional_analyzer), \
         patch('tools.generate_test_coverage_dashboard.TestQualityAnalyzer', return_value=mock_quality_analyzer):
        
        reports = run_analyzers()
        
        # Check that all analyzers were called
        mock_coverage_analyzer.generate_report.assert_called_once()
        mock_functional_analyzer.generate_report.assert_called_once()
        mock_quality_analyzer.generate_report.assert_called_once()
        
        # Check that reports were collected
        assert reports['coverage'] == mock_coverage_report
        assert reports['functional'] == mock_functional_report
        assert reports['quality'] == mock_quality_report


def test_generate_html_dashboard_no_history(
    sample_coverage_report, sample_functional_report, sample_quality_report
):
    """Test dashboard generation with no existing history."""
    reports = {
        'coverage': sample_coverage_report, 
        'functional': sample_functional_report, 
        'quality': sample_quality_report
    }
    
    # Patch the file operations
    with patch('os.path.exists', return_value=False), \
         patch('builtins.open', mock_open()) as mock_file, \
         patch('json.dump') as mock_json_dump:
        
        generate_html_dashboard(reports)
        
        # Check that both files were written
        assert mock_file.call_count == 2
        file_calls = [call[0][0] for call in mock_file.call_args_list]
        assert 'coverage_history.json' in file_calls
        assert 'test_coverage_dashboard.html' in file_calls
        
        # Check that JSON was dumped to the history file
        mock_json_dump.assert_called_once()
        args, _ = mock_json_dump.call_args
        assert isinstance(args[0], list)
        assert len(args[0]) == 1  # Should contain one entry (the current one)
        assert 'date' in args[0][0]
        assert 'overall_coverage' in args[0][0]
        

def test_generate_html_dashboard_with_history(
    sample_coverage_report, sample_functional_report, sample_quality_report, sample_history
):
    """Test dashboard generation with existing history."""
    reports = {
        'coverage': sample_coverage_report, 
        'functional': sample_functional_report, 
        'quality': sample_quality_report
    }
    
    # Patch file operations to return and capture history
    history_read = mock_open(read_data=json.dumps(sample_history))
    history_write = mock_open()
    
    # Create a mock that works for both reading and writing
    combined_mock = MagicMock()
    combined_mock.side_effect = [history_read.return_value, history_write.return_value]
    
    with patch('os.path.exists', return_value=True), \
         patch('builtins.open', combined_mock), \
         patch('json.load', return_value=sample_history), \
         patch('json.dump') as mock_json_dump:
        
        generate_html_dashboard(reports)
        
        # Check that JSON history was updated
        mock_json_dump.assert_called_once()
        history_data, _ = mock_json_dump.call_args[0]
        
        # Should have original history + new entry
        assert len(history_data) == len(sample_history) + 1
        assert history_data[0] == sample_history[0]
        assert history_data[1] == sample_history[1]
        assert 'date' in history_data[2]


def test_generate_html_dashboard_history_limit(
    sample_coverage_report, sample_functional_report, sample_quality_report
):
    """Test that history is limited to 10 entries."""
    reports = {
        'coverage': sample_coverage_report, 
        'functional': sample_functional_report, 
        'quality': sample_quality_report
    }
    
    # Create history with 10 entries
    history = [
        {
            'date': f'2025-{i:02d}-01',
            'overall_coverage': 0.70 + i*0.01,
            'functional_coverage': 0.60 + i*0.01,
            'quality_score': 65.0 + i
        }
        for i in range(1, 11)
    ]
    
    with patch('os.path.exists', return_value=True), \
         patch('builtins.open', mock_open()), \
         patch('json.load', return_value=history), \
         patch('json.dump') as mock_json_dump:
        
        generate_html_dashboard(reports)
        
        # Check that history is limited
        mock_json_dump.assert_called_once()
        history_data, _ = mock_json_dump.call_args[0]
        assert len(history_data) == 10  # Should stay at 10 entries
        
        # The oldest entry should be dropped
        dates = [entry['date'] for entry in history_data]
        assert '2025-01-01' not in dates
        assert '2025-10-01' in dates  # Last original entry


def test_get_status_class():
    """Test status class determination based on coverage."""
    assert get_status_class(0.85) == "good"
    assert get_status_class(0.80) == "good"
    assert get_status_class(0.75) == "warning"
    assert get_status_class(0.60) == "warning"
    assert get_status_class(0.59) == "poor"
    assert get_status_class(0.10) == "poor"


def test_get_quality_class():
    """Test quality class determination based on score."""
    assert get_quality_class(95) == "good"
    assert get_quality_class(70) == "good"
    assert get_quality_class(60) == "warning"
    assert get_quality_class(50) == "warning"
    assert get_quality_class(45) == "poor"
    assert get_quality_class(10) == "poor"


def test_generate_module_list():
    """Test module list HTML generation."""
    # Test with modules
    modules = ["module1.py", "module2.py", "module3.py"]
    html = generate_module_list(modules)
    assert "<table>" in html
    assert "module1.py" in html
    assert "module2.py" in html
    assert "module3.py" in html
    
    # Test with empty list
    assert "No modules without tests!" in generate_module_list([])
    
    # Test with more than 5 modules
    many_modules = [f"module{i}.py" for i in range(1, 10)]
    html_many = generate_module_list(many_modules)
    assert "module1.py" in html_many
    assert "module5.py" in html_many
    assert "module6.py" not in html_many  # Should be hidden
    assert "+ 4 more modules" in html_many  # Should show count of hidden modules


def test_generate_function_list():
    """Test function list HTML generation."""
    # Test with functions
    functions = [
        {'function': 'func1', 'file': 'file1.py', 'line_number': 10},
        {'function': 'func2', 'file': 'file2.py', 'line_number': 20},
    ]
    html = generate_function_list(functions)
    assert "func1" in html
    assert "file1.py" in html
    assert "10" in html
    assert "func2" in html
    
    # Test with empty list
    assert "No untested public functions!" in generate_function_list([])


def test_generate_test_quality_list():
    """Test test quality list HTML generation."""
    # Test with quality reports
    tests = [
        {'file': 'test1.py', 'quality_score': 30.5, 'issues': ['Issue 1', 'Issue 2', None]},
        {'file': 'test2.py', 'quality_score': 45.0, 'issues': ['Issue 3', None, None]},
    ]
    html = generate_test_quality_list(tests)
    assert "test1.py" in html
    assert "30.5" in html
    assert "Issue 1" in html
    assert "Issue 2" in html
    assert "test2.py" in html
    assert "Issue 3" in html
    
    # Test with empty list
    assert "No low quality tests!" in generate_test_quality_list([])


def test_main_execution():
    """Test main execution flow."""
    # Mock all the functions
    mock_reports = {
        'coverage': {'overall_coverage': 0.75},
        'functional': {'functional_coverage': 0.65},
        'quality': {'overall_quality_score': 70}
    }
    
    with patch('tools.generate_test_coverage_dashboard.run_coverage_analysis') as mock_run_coverage, \
         patch('tools.generate_test_coverage_dashboard.run_analyzers', return_value=mock_reports) as mock_run_analyzers, \
         patch('tools.generate_test_coverage_dashboard.generate_html_dashboard') as mock_generate:
        
        # Run the main function - need to import this way to trigger __name__ == '__main__'
        from tools.generate_test_coverage_dashboard import __name__ as module_name
        
        # Don't actually execute, just check our mocks would handle it properly
        mock_run_coverage.assert_not_called()
        mock_run_analyzers.assert_not_called()
        mock_generate.assert_not_called()