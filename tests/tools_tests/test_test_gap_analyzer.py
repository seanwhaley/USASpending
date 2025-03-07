"""Tests for the test gap analyzer tool."""
import os
import sys
import ast
import json
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock, call

# Ensure tools directory is in path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

from tools.test_gap_analyzer import (
    parse_python_file,
    find_implementation_files,
    find_test_file,
    analyze_coverage_gaps,
    main
)


@pytest.fixture
def sample_implementation():
    """Sample implementation file with classes and functions."""
    return """
class MyClass:
    def method1(self):
        pass
        
    def method2(self):
        pass
        
def standalone_function():
    pass
    
def another_function():
    return True
"""


@pytest.fixture
def sample_test():
    """Sample test file with test functions."""
    return """
def test_MyClass_method1():
    assert True
    
def test_standalone_function():
    assert True
    
class TestMyClass:
    def test_something(self):
        pass
"""


@pytest.fixture
def mock_file_structure():
    """Mock file structure for testing."""
    return {
        'src': {
            'module1.py': 'class Class1:\n    def method1(self): pass',
            'module2.py': 'def func1(): pass\ndef func2(): pass',
            'subdir': {
                'module3.py': 'class Class3:\n    def method3(self): pass'
            }
        },
        'tests': {
            'test_module1.py': 'def test_Class1(): pass',
            'subdir': {
                'test_module3.py': 'def test_Class3_method3(): pass'
            }
        }
    }


def setup_mock_filesystem(structure, base_path=''):
    """Set up a mock filesystem for testing."""
    paths = []
    
    def mock_walk(directory, *args, **kwargs):
        dir_path = os.path.normpath(directory)
        if base_path:
            # Remove base path prefix for comparison
            if dir_path.startswith(base_path):
                dir_path = dir_path[len(base_path):].lstrip(os.sep)
        
        # Find the subdirectory in our structure
        parts = dir_path.split(os.sep)
        current = structure
        
        try:
            for part in parts:
                if part:  # Skip empty parts
                    current = current[part]
            
            # Current is now the directory content
            if isinstance(current, dict):
                subdirs = [name for name, content in current.items() 
                          if isinstance(content, dict)]
                files = [name for name, content in current.items() 
                        if isinstance(content, str)]
                yield dir_path, subdirs, files
                
                # Recurse into subdirectories
                for subdir in subdirs:
                    subpath = os.path.join(dir_path, subdir)
                    yield from mock_walk(subpath)
        except (KeyError, TypeError):
            # Directory not found in our structure
            yield dir_path, [], []
    
    def mock_exists(path):
        path_str = str(path)
        if base_path and path_str.startswith(base_path):
            path_str = path_str[len(base_path):].lstrip(os.sep)
        
        parts = path_str.split(os.sep)
        current = structure
        
        try:
            for part in parts:
                if part:
                    current = current[part]
            return True
        except (KeyError, TypeError):
            return False
    
    def mock_open_impl(file_path, mode='r', *args, **kwargs):
        # Convert Path objects to string
        file_path = str(file_path)
        
        if base_path and file_path.startswith(base_path):
            file_path = file_path[len(base_path):].lstrip(os.sep)
        
        # Find content in structure
        parts = file_path.split(os.sep)
        current = structure
        
        try:
            for part in parts[:-1]:  # Navigate directories
                if part:
                    current = current[part]
            
            file_content = current[parts[-1]]
            return mock_open(read_data=file_content)(*args, **kwargs)
        except (KeyError, TypeError):
            return mock_open(read_data='')(*args, **kwargs)
    
    return mock_walk, mock_exists, mock_open_impl


def test_parse_python_file(sample_implementation, sample_test):
    """Test parsing Python files for class and function names."""
    # Test implementation file parsing
    with patch('builtins.open', mock_open(read_data=sample_implementation)):
        impl_names = parse_python_file('module.py')
    
    assert 'MyClass' in impl_names
    assert 'MyClass.method1' in impl_names
    assert 'MyClass.method2' in impl_names
    assert 'standalone_function' in impl_names
    assert 'another_function' in impl_names
    
    # Test test file parsing
    with patch('builtins.open', mock_open(read_data=sample_test)):
        test_names = parse_python_file('test_module.py')
    
    assert 'test_MyClass_method1' in test_names
    assert 'test_standalone_function' in test_names
    assert 'TestMyClass' in test_names
    assert 'TestMyClass.test_something' in test_names


def test_parse_python_file_syntax_error():
    """Test handling of syntax errors."""
    invalid_python = "def broken_function(:"
    
    with patch('builtins.open', mock_open(read_data=invalid_python)), \
         patch('builtins.print') as mock_print:
        names = parse_python_file('invalid.py')
    
    assert names == set()
    mock_print.assert_called_once_with("Error parsing invalid.py")


def test_find_implementation_files(mock_file_structure):
    """Test finding implementation files."""
    mock_walk, _, _ = setup_mock_filesystem(mock_file_structure)
    
    with patch('os.walk', mock_walk):
        impl_files = find_implementation_files('src')
    
    assert len(impl_files) == 3
    assert 'src/module1.py' in impl_files
    assert 'src/module2.py' in impl_files
    assert 'src/subdir/module3.py' in impl_files


def test_find_test_file(mock_file_structure):
    """Test finding corresponding test file."""
    mock_walk, _, _ = setup_mock_filesystem(mock_file_structure)
    
    with patch('os.walk', mock_walk):
        # Test with existing test file
        test_file = find_test_file('src/module1.py', 'tests')
        assert test_file == 'tests/test_module1.py'
        
        # Test with nested test file
        test_file = find_test_file('src/subdir/module3.py', 'tests')
        assert test_file == 'tests/subdir/test_module3.py'
        
        # Test with non-existent test file
        test_file = find_test_file('src/module2.py', 'tests')
        assert test_file == ""


def test_analyze_coverage_gaps(mock_file_structure):
    """Test analyzing coverage gaps."""
    mock_walk, mock_exists, mock_open_impl = setup_mock_filesystem(mock_file_structure)
    
    with patch('os.walk', mock_walk), \
         patch('builtins.open', mock_open_impl), \
         patch('pathlib.Path.exists', mock_exists):
        
        gaps = analyze_coverage_gaps('src', 'tests')
    
    # Check module1.py - should have missing Class1 method
    assert 'module1.py' in gaps
    assert 'Class1.method1' in gaps['module1.py']['missing_tests']
    
    # Check module2.py - no test file, all functions missing tests
    assert 'module2.py' in gaps
    assert gaps['module2.py']['test_file'] is None
    assert 'func1' in gaps['module2.py']['missing_tests']
    assert 'func2' in gaps['module2.py']['missing_tests']
    
    # Check module3.py - has test for method3, should not be in gaps
    assert 'subdir/module3.py' not in gaps


def test_main():
    """Test main function."""
    mock_walk, mock_exists, mock_open_impl = setup_mock_filesystem({
        'src': {'module.py': 'def untested(): pass'},
        'tests': {}
    }, base_path='/base')
    
    mock_args = MagicMock()
    mock_args.src_dir = 'src'
    mock_args.test_dir = 'tests'
    mock_args.output = None
    
    with patch('argparse.ArgumentParser.parse_args', return_value=mock_args), \
         patch('tools.test_gap_analyzer.Path.parent', MagicMock(Path('/base'))), \
         patch('os.walk', mock_walk), \
         patch('pathlib.Path.exists', return_value=True), \
         patch('builtins.open', mock_open_impl), \
         patch('builtins.print') as mock_print:
        
        exit_code = main()
    
    assert exit_code == 0
    # Should have printed output since no output file specified
    assert mock_print.call_count > 0


def test_main_with_output_file():
    """Test main function with output file."""
    mock_walk, mock_exists, mock_open_impl = setup_mock_filesystem({
        'src': {'module.py': 'def untested(): pass'},
        'tests': {}
    }, base_path='/base')
    
    mock_args = MagicMock()
    mock_args.src_dir = 'src'
    mock_args.test_dir = 'tests'
    mock_args.output = 'output.json'
    
    with patch('argparse.ArgumentParser.parse_args', return_value=mock_args), \
         patch('tools.test_gap_analyzer.Path.parent', MagicMock(Path('/base'))), \
         patch('os.walk', mock_walk), \
         patch('pathlib.Path.exists', return_value=True), \
         patch('builtins.open', mock_open_impl), \
         patch('json.dump') as mock_dump:
        
        exit_code = main()
    
    assert exit_code == 0
    # Should have called json.dump to write the file
    assert mock_dump.call_count == 1


def test_main_invalid_directories():
    """Test main function with invalid directories."""
    mock_args = MagicMock()
    mock_args.src_dir = 'nonexistent'
    mock_args.test_dir = 'tests'
    
    with patch('argparse.ArgumentParser.parse_args', return_value=mock_args), \
         patch('pathlib.Path.exists', return_value=False), \
         patch('builtins.print') as mock_print:
        
        exit_code = main()
    
    assert exit_code == 1
    # Should have printed error about missing directory
    assert mock_print.call_count > 0
    assert any('not found' in str(call) for call in mock_print.call_args_list)