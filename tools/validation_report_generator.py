"""Generate validation reports based on test results and coverage data."""

import json
import os
from pathlib import Path
from datetime import datetime


def generate_validation_report():
    """Generate validation reports based on test results and coverage."""
    print("Generating validation reports...")
    
    # Create output directory
    output_dir = Path("output/reports/validation")
    output_dir.mkdir(exist_ok=True, parents=True)
    
    # Load coverage data
    try:
        with open("output/reports/coverage/coverage.json", "r", encoding='utf-8') as f:
            coverage_data = json.load(f)
    except FileNotFoundError:
        coverage_data = {}
        print("Warning: Coverage data not found")
    
    # Load test quality data
    try:
        with open("output/reports/test_quality/test_quality_report.json", "r", encoding='utf-8') as f:
            quality_data = json.load(f)
    except FileNotFoundError:
        quality_data = {}
        print("Warning: Test quality data not found")
    
    # Create validation report
    validation_report = {
        "timestamp": datetime.now().isoformat(),
        "validation_summary": {
            "passed": True,  # Default to True, set to False if any validation fails
            "coverage_threshold_met": False,
            "quality_threshold_met": False,
            "validation_checks": []
        }
    }
    
    # Validate coverage
    if coverage_data:
        try:
            total_coverage = coverage_data.get("totals", {}).get("percent_covered", 0)
            validation_report["validation_summary"]["coverage_threshold_met"] = total_coverage >= 70
            validation_report["validation_summary"]["passed"] &= validation_report["validation_summary"]["coverage_threshold_met"]
            
            validation_report["validation_summary"]["validation_checks"].append({
                "name": "coverage_threshold",
                "passed": validation_report["validation_summary"]["coverage_threshold_met"],
                "threshold": 70,
                "actual": total_coverage,
                "message": f"Coverage is {total_coverage:.1f}% (threshold: 70%)"
            })
        except (KeyError, AttributeError) as e:
            print(f"Error processing coverage data: {e}")
    
    # Validate test quality
    if quality_data:
        try:
            quality_score = quality_data.get("overall_quality_score", 0)
            validation_report["validation_summary"]["quality_threshold_met"] = quality_score >= 60
            validation_report["validation_summary"]["passed"] &= validation_report["validation_summary"]["quality_threshold_met"]
            
            validation_report["validation_summary"]["validation_checks"].append({
                "name": "quality_threshold",
                "passed": validation_report["validation_summary"]["quality_threshold_met"],
                "threshold": 60,
                "actual": quality_score,
                "message": f"Test quality score is {quality_score:.1f} (threshold: 60)"
            })
        except (KeyError, AttributeError) as e:
            print(f"Error processing test quality data: {e}")
    
    # Save validation report
    validation_file = output_dir / "validation_report.json"
    with open(validation_file, "w", encoding='utf-8') as f:
        json.dump(validation_report, f, indent=2)
    
    # Generate summary file
    summary_file = output_dir / "validation_summary.txt"
    with open(summary_file, "w", encoding='utf-8') as f:
        f.write(f"Validation Report: {'PASSED' if validation_report['validation_summary']['passed'] else 'FAILED'}\n")
        f.write(f"Generated: {validation_report['timestamp']}\n\n")
        
        for check in validation_report["validation_summary"]["validation_checks"]:
            status = "✓" if check["passed"] else "✗"
            f.write(f"{status} {check['message']}\n")
    
    print(f"Validation reports saved to {output_dir}")
    return validation_report


if __name__ == "__main__":
    report = generate_validation_report()
    status = "PASSED" if report["validation_summary"]["passed"] else "FAILED"
    print(f"Validation {status}")
