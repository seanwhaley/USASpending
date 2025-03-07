@echo off
REM Run all test analysis tools and generate dashboard

echo ===================================================
echo        USASpending Test Analysis Dashboard
echo ===================================================
echo.

REM Set working directory to project root
cd /d "d:\VS Code Projects\USASpending"

echo Installing required packages...
pip install pytest pytest-cov

REM Clean up any duplicate files from previous runs
echo.
echo Cleaning up any duplicate output files...
python -m tools.cleanup_duplicate_files

echo.
echo Running test analysis and generating dashboard...
echo This may take a few minutes depending on your test suite size.
echo.

REM Create output directories if they don't exist
mkdir output\reports\coverage 2>nul
mkdir output\reports\test_quality 2>nul
mkdir output\reports\validation 2>nul

REM Run coverage analysis
python -m pytest --cov=src --cov-report=json:output/reports/coverage/coverage.json --cov-report=xml:output/reports/coverage/coverage.xml

REM Run test analysis tools
python -m tools.functional_coverage_analyzer
python -m tools.test_gap_analyzer
python -m tools.test_quality_analyzer
python -m tools.test_coverage_analyzer

REM Generate validation reports
python -m tools.validation_report_generator

REM Generate dashboard
python -m tools.generate_test_coverage_dashboard

echo.
echo ===================================================
echo Analysis complete!
echo Reports saved to:
echo - output/reports/coverage/test_gap_report.json
echo - output/reports/coverage/functional_coverage_report.json
echo - output/reports/coverage/coverage_report.json
echo - output/reports/test_quality/test_quality_report.json
echo - output/reports/validation/validation_report.json
echo - output/reports/validation/validation_summary.txt
echo - output/reports/coverage/coverage.xml
echo - output/reports/coverage_history.json
echo - output/reports/test_coverage_dashboard.html
echo ===================================================

echo Opening dashboard in default browser...
start "" "output\reports\test_coverage_dashboard.html"
echo.
pause