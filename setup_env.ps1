#!/usr/bin/env pwsh

# Set PYTHONPATH for the current session
#$env:PYTHONPATH = "src;tools"

# Set PYTHONPATH permanently at machine level (requires administrator privileges)
# Uncomment the following line if you want to set it permanently
# [System.Environment]::SetEnvironmentVariable("PYTHONPATH", "src;tools", [System.EnvironmentVariableTarget]::Machine)

# Stop on first error
$ErrorActionPreference = "Stop"

# Configuration
$VENV_NAME = ".venv"
$PYTHON_VERSION = "3.13"
$REQUIREMENTS_FILE = "requirements.txt"
$DEV_REQUIREMENTS_FILE = "requirements-dev.txt"

# Utility functions
function Write-Step {
    param($Message)
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Test-Command {
    param($Command)
    return [bool](Get-Command -Name $Command -ErrorAction SilentlyContinue)
}

# Check Python installation
Write-Step "Checking Python installation..."
if (-not (Test-Command "python")) {
    Write-Error "Python is not installed or not in PATH"
    exit 1
}

$pythonVersion = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ([version]$pythonVersion -lt [version]$PYTHON_VERSION) {
    Write-Error "Python $PYTHON_VERSION or higher is required (found $pythonVersion)"
    exit 1
}

# Create virtual environment if it doesn't exist
Write-Step "Setting up virtual environment..."
if (-not (Test-Path $VENV_NAME)) {
    python -m venv $VENV_NAME
    if (-not $?) {
        Write-Error "Failed to create virtual environment"
        exit 1
    }
}

# Activate virtual environment
Write-Step "Activating virtual environment..."
$activateScript = Join-Path $VENV_NAME "Scripts\Activate.ps1"
. $activateScript

# Upgrade pip
Write-Step "Upgrading pip..."
python -m pip install --upgrade pip
if (-not $?) {
    Write-Error "Failed to upgrade pip"
    exit 1
}

# Install dependencies
Write-Step "Installing dependencies..."
if (Test-Path $REQUIREMENTS_FILE) {
    pip install -r $REQUIREMENTS_FILE
    if (-not $?) {
        Write-Error "Failed to install dependencies"
        exit 1
    }
}

# Install development dependencies
Write-Step "Installing development dependencies..."
if (Test-Path $DEV_REQUIREMENTS_FILE) {
    pip install -r $DEV_REQUIREMENTS_FILE
    if (-not $?) {
        Write-Error "Failed to install development dependencies"
        exit 1
    }
}

# Install the package in development mode
Write-Step "Installing package in development mode..."
pip install -e .
if (-not $?) {
    Write-Error "Failed to install package in development mode"
    exit 1
}

# Create directories if they don't exist
Write-Step "Creating project directories..."
$directories = @("logs", "output", "output/entities")
foreach ($dir in $directories) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir
    }
}

# Run tests to verify installation
Write-Step "Running tests..."
python -m pytest tests/
if (-not $?) {
    Write-Warning "Some tests failed, but continuing..."
}

Write-Host "`nSetup completed successfully!" -ForegroundColor Green
Write-Host "To activate the virtual environment, run: .\.venv\Scripts\Activate.ps1"