"""Tests for report generators."""

import os
import json
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock

from tools.reports import (
    ValidationReportGenerator,
    DashboardGenerator
)

@pytest.fixture
def sample_coverage_data():
    """Sample coverage report data."""
    return {
        'coverage_percent': 75.5,
        'files': {
            'src/module_a.py': {
                'summary': {
                    'percent_covered': 80.0
                }
            }
        }
    }

@pytest.fixture
def sample_quality_data():
    """Sample quality report data."""
    return {
        'overall_quality_score': 65.0,
        'low_quality_tests': []
    }

@pytest.fixture
def sample_gap_data():
    """Sample gap report data."""
    return {
        'gaps': ['module_b.py']
    }

def test_validation_report_generator(tmp_path, sample_coverage_data, sample_quality_data, sample_gap_data):
    """Test ValidationReportGenerator functionality."""
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    
    # Create sample report files
    (reports_dir / "coverage").mkdir()
    (reports_dir / "test_quality").mkdir()
    
    with open(reports_dir / "coverage" / "coverage_report.json", "w") as f:
        json.dump(sample_coverage_data, f)
    with open(reports_dir / "test_quality" / "test_quality_report.json", "w") as f:
        json.dump(sample_quality_data, f)
    with open(reports_dir / "coverage" / "test_gap_report.json", "w") as f:
        json.dump(sample_gap_data, f)
    
    # Run validation report generator
    generator = ValidationReportGenerator(str(reports_dir / "validation"))
    report = generator.generate_report()
    
    assert 'validation_summary' in report
    assert 'passed_checks' in report['validation_summary']
    assert 'validation_checks' in report['validation_summary']
    
    # Verify thresholds were checked
    checks = report['validation_summary']['validation_checks']
    assert any(c['name'] == 'coverage_threshold' for c in checks)
    assert any(c['name'] == 'test_quality_threshold' for c in checks)
    assert any(c['name'] == 'no_test_gaps' for c in checks)

def test_dashboard_generator(tmp_path):
    """Test DashboardGenerator functionality."""
    output_dir = tmp_path / "output"
    static_dir = tmp_path / "static" / "tests_dashboard"
    
    # Create required directories and files
    for d in [output_dir, static_dir / "css", static_dir / "js", static_dir / "templates"]:
        d.mkdir(parents=True)
    
    # Create sample static files
    (static_dir / "css" / "style.css").touch()
    (static_dir / "js" / "main.js").touch()
    
    # Create sample template
    template_content = '''
    <html>
    <body>
        <h1>Test Coverage Dashboard</h1>
        <div id="coverage">{{ coverage }}</div>
    </body>
    </html>
    '''
    (static_dir / "templates" / "dashboard.html").write_text(template_content)
    
    # Initialize generator
    generator = DashboardGenerator(
        template_dir=str(static_dir / "templates"),
        output_dir=str(output_dir)
    )
    
    # Generate dashboard
    generator.generate_dashboard()
    
    # Verify output
    dashboard_dir = output_dir / "tests_dashboard"
    assert dashboard_dir.exists()
    assert (dashboard_dir / "css").exists()
    assert (dashboard_dir / "js").exists()
    assert (dashboard_dir / "js" / "config.js").exists()
    
    # Verify AI summary was generated
    assert (dashboard_dir / "ai_test_summary.json").exists()

def test_validation_report_thresholds(tmp_path):
    """Test validation report threshold customization."""
    generator = ValidationReportGenerator(str(tmp_path))
    
    # Test custom thresholds
    generator.thresholds = {
        'min_coverage': 90.0,
        'critical_modules_coverage': 95.0,
        'min_quality_score': 80.0
    }
    
    # Create sample data that fails higher thresholds
    coverage_data = {'coverage_percent': 85.0}
    quality_data = {'overall_quality_score': 75.0}
    gap_data = {'gaps': []}
    
    with patch('tools.common.FileHelper.load_json_file') as mock_load:
        mock_load.side_effect = [coverage_data, quality_data, gap_data]
        
        report = generator.generate_report()
        
        # Should fail coverage and quality checks with higher thresholds
        assert not any(
            check['passed'] 
            for check in report['validation_summary']['validation_checks']
            if check['name'] in ['coverage_threshold', 'test_quality_threshold']
        )

def test_dashboard_config_generation(tmp_path):
    """Test dashboard configuration file generation."""
    generator = DashboardGenerator(
        template_dir=str(tmp_path / "templates"),
        output_dir=str(tmp_path)
    )
    
    # Create minimal directory structure
    dashboard_dir = tmp_path / "tests_dashboard"
    (dashboard_dir / "js").mkdir(parents=True)
    
    # Generate config
    generator._create_config(dashboard_dir)
    
    # Verify config file
    config_file = dashboard_dir / "js" / "config.js"
    assert config_file.exists()
    
    # Check config content
    config_content = config_file.read_text()
    assert 'const CONFIG = ' in config_content
    assert 'dataPaths' in config_content
    assert 'environment' in config_content
    assert 'dashboardVersion' in config_content