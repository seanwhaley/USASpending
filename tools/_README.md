# Test Tools

This directory contains tools for running tests, analyzing test coverage, and generating reports.

## File Structure

```
tools/
├── __init__.py              # Package initialization
├── analyzers.py            # Core analysis functionality
│   ├── CoverageAnalyzer
│   ├── TestQualityAnalyzer
│   ├── TestGapAnalyzer
│   └── FunctionalCoverageAnalyzer
├── common.py               # Shared utilities and base classes
├── reports.py             # Report generation and dashboard tools
│   ├── ValidationReportGenerator
│   └── DashboardGenerator
└── Entry Points
    ├── run_test_pipeline.py    # Main pipeline orchestrator
    ├── run_tests.py            # Run test suite
    ├── generate_coverage.py    # Generate coverage reports
    ├── analyze_test_quality.py # Analyze test quality
    └── validate_coverage.py    # Validate coverage thresholds
```

## Core Components

### Analyzers (`analyzers.py`)
Contains all analysis functionality:
- `CoverageAnalyzer`: Analyzes test coverage from coverage.xml files
- `TestQualityAnalyzer`: Evaluates test quality metrics
- `TestGapAnalyzer`: Identifies modules lacking tests
- `FunctionalCoverageAnalyzer`: Analyzes functional test coverage

### Common (`common.py`)
Shared utilities and base classes:
- Environment detection
- Directory/file helpers
- Base report class
- JSON file operations
- Project path helpers

### Reports (`reports.py`)
Report generation and dashboard functionality:
- `ValidationReportGenerator`: Validates test metrics against thresholds
- `DashboardGenerator`: Creates interactive test dashboard
- Coverage history management

## Entry Points

### Main Pipeline (`run_test_pipeline.py`)
Orchestrates the complete test analysis pipeline with options to:
- Run tests
- Generate coverage reports
- Analyze test quality
- Find test gaps
- Validate coverage
- Update history
- Generate dashboard

### Individual Tools
- `run_tests.py`: Run the test suite using pytest
- `generate_coverage.py`: Generate coverage reports
- `analyze_test_quality.py`: Run test quality analysis
- `validate_coverage.py`: Validate coverage against thresholds

## Usage

1. Run complete pipeline:
```bash
python -m tools.run_test_pipeline
```

2. Run individual steps:
```bash
python -m tools.run_tests           # Run tests
python -m tools.generate_coverage   # Generate coverage
python -m tools.analyze_test_quality # Analyze quality
python -m tools.validate_coverage   # Validate coverage
```

## Configuration

The tools use several environment variables for configuration:
- `CI`: Detected automatically in CI/CD environments
- `PRODUCTION`: Set to run in production mode
- Custom thresholds can be configured in ValidationReportGenerator

## Output

Reports are generated in the following structure:
```
output/test_dashboard
├── coverage/
│   ├── coverage.xml
│   ├── coverage.json
│   ├── coverage_report.json
│   ├── test_gap_report.json
│   └── functional_coverage_report.json
├── test_quality/
│   └── test_quality_report.json
├── validation/
│   └── validation_report.json
└── tests_dashboard/
    ├── index.html
    ├── css/
    ├── js/
    └── data/
```
