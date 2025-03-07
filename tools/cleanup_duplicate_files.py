#!/usr/bin/env python
"""Script to clean up duplicate output files from the project root."""
import os
from pathlib import Path

def cleanup_duplicates():
    """Remove duplicate output files from project root that should be in output/reports folders."""
    project_root = Path(__file__).parent.parent
    files_to_remove = [
        'coverage_history.json',
        'coverage_report.json',
        'coverage.json',
        'coverage.xml',
        'functional_coverage_report.json',
        'test_quality_report.json'
    ]
    
    print("Cleaning up duplicate output files from project root...")
    for filename in files_to_remove:
        file_path = project_root / filename
        if file_path.exists():
            try:
                file_path.unlink()
                print(f"Deleted: {file_path}")
            except Exception as e:
                print(f"Error deleting {file_path}: {e}")
        else:
            print(f"File not found: {file_path}")
    
    print("Cleanup complete.")

if __name__ == "__main__":
    cleanup_duplicates()
