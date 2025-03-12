"""Tests for tool entry point functions."""

import pytest
from unittest.mock import patch, MagicMock

from tools.run_tests import run_test_suite
from tools.generate_coverage import generate_coverage_reports
from tools.analyze_test_quality import analyze_test_quality
from tools.validate_coverage import validate_coverage_thresholds

def test_run_test_suite():
    """Test test suite runner."""
    with patch('pytest.main') as mock_pytest:
        mock_pytest.return_value = 0  # Success
        assert run_test_suite() is True
        
        mock_pytest.return_value = 1  # Failure
        assert run_test_suite() is False

def test_generate_coverage_reports(tmp_path):
    """Test coverage report generation."""
    reports_dir = tmp_path / "reports" / "coverage"
    
    with patch('pytest.main') as mock_pytest:
        mock_pytest.return_value = 0
        
        with patch.dict('os.environ', {'COVERAGE_FILE': str(reports_dir / '.coverage')}):
            assert generate_coverage_reports() is True
            
            # Verify pytest was called with correct parameters
            mock_pytest.assert_called_once()
            args = mock_pytest.call_args[0][0]
            assert '--cov=src' in args
            assert '--cov-branch' in args
            assert any('coverage.xml' in arg for arg in args)
            assert any('coverage.json' in arg for arg in args)

def test_analyze_test_quality():
    """Test test quality analysis."""
    with patch('tools.analyzers.TestQualityAnalyzer') as MockAnalyzer:
        mock_analyzer = MagicMock()
        MockAnalyzer.return_value = mock_analyzer
        
        mock_analyzer.generate_report.return_value = {
            'overall_quality_score': 75.0,
            'low_quality_tests': []
        }
        
        assert analyze_test_quality() is True
        mock_analyzer.generate_report.assert_called_once()

def test_validate_coverage_thresholds():
    """Test coverage threshold validation."""
    with patch('tools.reports.ValidationReportGenerator') as MockGenerator:
        mock_generator = MagicMock()
        MockGenerator.return_value = mock_generator
        
        # Test passing validation
        mock_generator.generate_report.return_value = {
            'validation_summary': {
                'passed': True,
                'validation_checks': [
                    {'name': 'coverage_threshold', 'passed': True}
                ]
            }
        }
        assert validate_coverage_thresholds() is True
        
        # Test failing validation
        mock_generator.generate_report.return_value = {
            'validation_summary': {
                'passed': False,
                'validation_checks': [
                    {'name': 'coverage_threshold', 'passed': False}
                ]
            }
        }
        assert validate_coverage_thresholds() is False