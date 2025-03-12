@echo off
REM Run test analysis tools and generate dashboard

setlocal enabledelayedexpansion

REM Parse command line arguments
set "RUN_COVERAGE=1"
set "RUN_QUALITY=1"
set "RUN_GAPS=1"
set "RUN_FUNCTIONAL=1"
set "RUN_VALIDATION=1"
set "GENERATE_DASHBOARD=1"
set "OPEN_DASHBOARD=1"
set "HAD_ERRORS=0"

:parse_args
if "%~1"=="" goto continue
if /i "%~1"=="--help" goto show_help
if /i "%~1"=="--skip-coverage" set "RUN_COVERAGE=0"
if /i "%~1"=="--skip-quality" set "RUN_QUALITY=0"
if /i "%~1"=="--skip-gaps" set "RUN_GAPS=0"
if /i "%~1"=="--skip-functional" set "RUN_FUNCTIONAL=0"
if /i "%~1"=="--skip-validation" set "RUN_VALIDATION=0"
if /i "%~1"=="--skip-dashboard" set "GENERATE_DASHBOARD=0"
if /i "%~1"=="--no-open" set "OPEN_DASHBOARD=0"
shift
goto parse_args

:show_help
echo Usage: %~nx0 [options]
echo Options:
echo   --help               Show this help message
echo   --skip-coverage     Skip coverage analysis
echo   --skip-quality      Skip test quality analysis
echo   --skip-gaps         Skip test gap analysis
echo   --skip-functional   Skip functional coverage analysis
echo   --skip-validation   Skip validation checks
echo   --skip-dashboard    Skip dashboard generation
echo   --no-open          Don't open dashboard in browser
goto end

:continue
echo ===================================================
echo        USASpending Test Analysis Dashboard
echo ===================================================
echo.

REM Set working directory to project root
cd /d "%~dp0"

echo Installing required packages...
pip install pytest pytest-cov >nul

echo.
echo Running test analysis and generating dashboard...
echo This may take a few minutes depending on your test suite size.
echo.

REM Run coverage analysis if requested
if %RUN_COVERAGE%==1 (
    echo Running test coverage analysis...
    python -m tools run_tests
    if errorlevel 1 (
        echo Warning: Test coverage analysis had errors
        set "HAD_ERRORS=1"
    ) else (
        echo Coverage reports generated in output/test_dashboard/results/coverage
    )
)

REM Run test quality analysis if requested
if %RUN_QUALITY%==1 (
    echo Running test quality analysis...
    python -m tools analyze_test_quality
    if errorlevel 1 (
        echo Warning: Test quality analysis had errors
        set "HAD_ERRORS=1"
    ) else (
        echo Test quality report generated in output/test_dashboard/results/test_quality
    )
)

REM Run gap analysis if requested
if %RUN_GAPS%==1 (
    echo Running gap analysis...
    python -m tools gap_analysis
    if errorlevel 1 (
        echo Warning: Gap analysis had errors
        set "HAD_ERRORS=1"
    ) else (
        echo Test gap report generated in output/test_dashboard/results/coverage
    )
)

REM Run functional coverage analysis if requested
if %RUN_FUNCTIONAL%==1 (
    echo Generating functional coverage analysis...
    python -m tools functional_analysis
    if errorlevel 1 (
        echo Warning: Functional coverage analysis had errors
        set "HAD_ERRORS=1"
    ) else (
        echo Functional coverage report generated in output/test_dashboard/results/functional
    )
)

REM Run validation if requested
if %RUN_VALIDATION%==1 (
    echo Validating coverage thresholds...
    python -m tools validate_coverage
    if errorlevel 1 (
        echo Warning: Coverage validation had errors
        set "HAD_ERRORS=1"
    ) else (
        echo Validation report generated in output/test_dashboard/results/validation
    )
)

REM Generate dashboard if requested
if %GENERATE_DASHBOARD%==1 (
    echo.
    echo Generating dashboard...
    python -m tools generate_dashboard
    if errorlevel 1 (
        echo Warning: Dashboard generation had errors
        set "HAD_ERRORS=1"
    ) else (
        echo.
        echo ===================================================
        echo Dashboard generation complete
        echo Dashboard files available at output/test_dashboard/index.html
        echo ===================================================
        echo.

        if %OPEN_DASHBOARD%==1 (
            echo Opening dashboard in default browser...
            start "" "output\test_dashboard\index.html"
        )
    )
) else (
    echo.
    echo ===================================================
    echo Test analysis complete! Dashboard generation skipped.
    echo Run without --skip-dashboard to generate the dashboard.
    echo ===================================================
    echo.
)

:end
if %HAD_ERRORS%==1 (
    echo.
    echo ===================================================
    echo Warning: Some components reported errors.
    echo The dashboard may show partial or incomplete data.
    echo See above messages for details.
    echo ===================================================
)
echo.
pause