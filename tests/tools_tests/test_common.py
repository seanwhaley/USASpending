"""Tests for common utility functions and classes."""

import os
import json
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open

from tools.common import (
    detect_environment,
    DirectoryHelper,
    FileHelper,
    BaseReport,
    JSONFileOperations,
    ProjectPathHelper
)

def test_detect_environment():
    """Test environment detection."""
    # Test CI detection
    with patch.dict(os.environ, {'CI': 'true'}):
        assert detect_environment() == 'ci'
    
    # Test production detection
    with patch.dict(os.environ, {'ENV': 'production'}):
        assert detect_environment() == 'production'
    
    # Test development (default)
    with patch.dict(os.environ, {}, clear=True):
        assert detect_environment() == 'development'

def test_directory_helper(tmp_path):
    """Test DirectoryHelper functionality."""
    test_dir = tmp_path / "test_dir"
    
    # Test ensure_dir
    created_path = DirectoryHelper.ensure_dir(test_dir)
    assert created_path.exists()
    assert created_path.is_dir()
    
    # Test get_project_root
    root = DirectoryHelper.get_project_root()
    assert root.exists()
    assert (root / "tools").exists()
    
    # Test get_reports_dir
    reports_dir = DirectoryHelper.get_reports_dir()
    assert reports_dir.parent.name == "output"
    assert reports_dir.name == "reports"

def test_file_helper(tmp_path):
    """Test FileHelper functionality."""
    test_file = tmp_path / "test.json"
    test_data = {"key": "value"}
    
    # Test save_json_report
    FileHelper.save_json_report(test_data, test_file)
    assert test_file.exists()
    assert json.loads(test_file.read_text()) == test_data
    
    # Test load_json_file
    loaded_data = FileHelper.load_json_file(test_file)
    assert loaded_data == test_data
    
    # Test load_json_file with nonexistent file
    nonexistent = FileHelper.load_json_file(tmp_path / "nonexistent.json")
    assert nonexistent == {}
    
    # Test load_json_file with default
    default = {"default": True}
    nonexistent_with_default = FileHelper.load_json_file(
        tmp_path / "nonexistent.json",
        default
    )
    assert nonexistent_with_default == default

def test_base_report(tmp_path):
    """Test BaseReport functionality."""
    report = BaseReport(tmp_path)
    
    assert report.output_dir == tmp_path
    assert report.environment in ['ci', 'production', 'development']
    assert report.timestamp is not None
    
    # Test save_report
    test_data = {"test": True}
    report.save_report(test_data, "test.json")
    saved_file = tmp_path / "test.json"
    assert saved_file.exists()
    assert json.loads(saved_file.read_text()) == test_data

def test_json_file_operations():
    """Test JSONFileOperations functionality."""
    test_data = {}
    
    # Test add_common_report_data
    with patch.dict(os.environ, {'USERNAME': 'testuser'}):
        result = JSONFileOperations.add_common_report_data(test_data)
        assert 'timestamp' in result
        assert result['environment'] in ['ci', 'production', 'development']
        assert result['generated_by'] == 'testuser'

def test_project_path_helper(tmp_path):
    """Test ProjectPathHelper functionality."""
    # Test get_project_root
    root = ProjectPathHelper.get_project_root()
    assert root.exists()
    assert (root / "tools").exists()
    
    # Test get_reports_dir
    reports_dir = ProjectPathHelper.get_reports_dir()
    assert reports_dir.parent.name == "output"
    assert reports_dir.name == "reports"
    
    # Test get_relative_path
    test_file = tmp_path / "subdir" / "test.txt"
    rel_path = ProjectPathHelper.get_relative_path(test_file, tmp_path)
    assert rel_path == "subdir/test.txt"