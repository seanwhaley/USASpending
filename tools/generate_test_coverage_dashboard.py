"""Generate a comprehensive test coverage dashboard HTML file."""

import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from jinja2 import Template, Environment, FileSystemLoader

from .test_coverage_analyzer import TestCoverageAnalyzer
from .test_quality_analyzer import TestQualityAnalyzer

def run_coverage_analysis():
    """Run pytest with coverage and generate reports"""
    print("Running test coverage analysis...")
    
    os.makedirs("output/reports/coverage", exist_ok=True)
    
    # Run pytest with coverage reporting
    subprocess.run([
        "pytest", 
        "--cov=src", 
        "--cov-branch",
        "--cov-report=json:output/reports/coverage/coverage.json",
        "--cov-report=xml:output/reports/coverage/coverage.xml",
        "tests/"
    ])

def collect_reports():
    """Collect all report data from various tools"""
    print("Collecting all test reports...")
    data = {}
    
    # Coverage data
    try:
        with open("output/reports/coverage/coverage.json", "r") as f:
            data["coverage"] = json.load(f)
    except FileNotFoundError:
        print("Warning: Coverage data not found")
        data["coverage"] = {}
    
    # Test quality data
    try:
        with open("output/reports/test_quality/test_quality_report.json", "r") as f:
            data["quality"] = json.load(f)
    except FileNotFoundError:
        print("Warning: Test quality data not found")
        data["quality"] = {}
    
    # Test gap data
    try:
        with open("output/reports/coverage/test_gap_report.json", "r") as f:
            data["gaps"] = json.load(f)
    except FileNotFoundError:
        print("Warning: Test gap report not found")
        data["gaps"] = {}
    
    # Validation data
    try:
        with open("output/reports/validation/validation_report.json", "r") as f:
            data["validation"] = json.load(f)
    except FileNotFoundError:
        print("Warning: Validation report not found")
        data["validation"] = {}
    
    # Functional coverage data
    try:
        with open("output/reports/coverage/functional_coverage_report.json", "r") as f:
            data["functional"] = json.load(f)
    except FileNotFoundError:
        print("Warning: Functional coverage report not found")
        data["functional"] = {}
    
    # Get coverage history if available
    try:
        with open("output/reports/coverage_history.json", "r") as f:
            history_data = json.load(f)
            if isinstance(history_data, dict):
                data["history"] = history_data
            else:
                data["history"] = {"dates": [], "coverage": []}
    except FileNotFoundError:
        data["history"] = {"dates": [], "coverage": []}
    
    # Add current coverage to history if we have it
    if data["coverage"] and "totals" in data["coverage"]:
        current_date = datetime.now().strftime("%Y-%m-%d")
        coverage_value = data["coverage"]["totals"]["percent_covered"]
        
        # Initialize history structure if needed
        if "dates" not in data["history"]:
            data["history"]["dates"] = []
        if "coverage" not in data["history"]:
            data["history"]["coverage"] = []
            
        # Only add if date not already present
        if current_date not in data["history"]["dates"]:
            data["history"]["dates"].append(current_date)
            data["history"]["coverage"].append(coverage_value)
            
            # Save updated history
            os.makedirs(os.path.dirname("output/reports/coverage_history.json"), exist_ok=True)
            with open("output/reports/coverage_history.json", "w") as f:
                json.dump(data["history"], f)
    
    return data

def prepare_template_data(data):
    """Prepare data for template rendering"""
    from jinja2 import Markup
    
    summary = {
        "generation_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_coverage": f"{data['coverage'].get('totals', {}).get('percent_covered', 0):.1f}" if data["coverage"] else "0.0",
        "coverage_status_class": (
            'success' if float(data['coverage'].get('totals', {}).get('percent_covered', 0)) >= 80 else 
            'warning' if float(data['coverage'].get('totals', {}).get('percent_covered', 0)) >= 60 else 
            'error'
        ),
        "test_quality_score": f"{data['quality'].get('overall_quality_score', 0):.1f}" if data["quality"] else "0.0",
        "quality_status_class": (
            'success' if float(data['quality'].get('overall_quality_score', 0)) >= 80 else 
            'warning' if float(data['quality'].get('overall_quality_score', 0)) >= 60 else 
            'error'
        ),
        "modules_without_tests": len(data["gaps"]) if data["gaps"] else 0,
        "gaps_status_class": (
            'success' if len(data["gaps"] or []) == 0 else 
            'warning' if len(data["gaps"] or []) <= 3 else 
            'error'
        ),
        "validation_passed": data["validation"].get("validation_summary", {}).get("passed", False) if data["validation"] else False,
        "validation_status_class": 'success' if data["validation"].get("validation_summary", {}).get("passed", False) else 'error',
        "validation_status_icon": '✓' if data["validation"].get("validation_summary", {}).get("passed", False) else '✗',
        "chart_data": json.dumps({
            "dates": data["history"]["dates"],
            "coverage": data["history"]["coverage"]
        })
    }

    # Generate validation checks HTML
    validation_checks_html = []
    if data["validation"] and "validation_summary" in data["validation"] and "validation_checks" in data["validation"]["validation_summary"]:
        for check in data["validation"]["validation_summary"]["validation_checks"]:
            alert_class = "usa-alert--success" if check["passed"] else "usa-alert--error"
            icon = '✓' if check["passed"] else '✗'
            validation_checks_html.append(
                f'<div class="usa-alert {alert_class} margin-bottom-2" role="status">'
                f'<div class="usa-alert__body">'
                f'<p class="usa-alert__text">{icon} {check["message"]}</p>'
                f'</div></div>'
            )
    else:
        validation_checks_html.append(
            '<div class="usa-alert usa-alert--info" role="status">'
            '<div class="usa-alert__body">'
            '<p class="usa-alert__text">No validation data available</p>'
            '</div></div>'
        )
    summary["validation_checks_html"] = "".join(validation_checks_html)  # Changed from join with newline

    # Generate module coverage HTML
    module_coverage_html = []
    if data["coverage"] and "files" in data["coverage"]:
        # Sort files by coverage for better visualization
        sorted_files = sorted(
            [(path, info) for path, info in data["coverage"]["files"].items() if path.startswith("src/")],
            key=lambda x: x[1]["summary"]["percent_covered"]
        )
        
        if sorted_files:
            for file_path, file_data in sorted_files:
                module_name = file_path[4:].replace("/", ".")
                coverage = file_data["summary"]["percent_covered"]
                missing_lines = len(file_data["missing_lines"]) if "missing_lines" in file_data else 0
                
                status_class = (
                    'success' if coverage >= 80 else 
                    'warning' if coverage >= 60 else 
                    'error'
                )
                
                module_coverage_html.append(
                    f'<tr>'
                    f'<th scope="row" class="font-mono-sm">{module_name}</th>'
                    f'<td class="text-center">'
                    f'<span class="usa-tag usa-tag--big metric-value {status_class}" style="font-size: 1rem">'
                    f'{coverage:.1f}%'
                    f'</span>'
                    f'</td>'
                    f'<td class="text-right font-mono-sm">{missing_lines}</td>'
                    f'</tr>'
                )
        else:
            module_coverage_html.append(
                '<tr><td colspan="3" class="text-center">No source files found with prefix "src/"</td></tr>'
            )
    else:
        module_coverage_html.append(
            '<tr><td colspan="3" class="text-center">No coverage data available</td></tr>'
        )
    summary["module_coverage_html"] = "".join(module_coverage_html)  # Changed from join with newline

    # Add functional coverage HTML
    functional_coverage_html = []
    if data["functional"] and "features" in data["functional"]:
        functional_coverage_html.append('<div class="grid-row grid-gap">')
        for feature, details in data["functional"]["features"].items():
            coverage_pct = details.get("coverage_percent", 0)
            status_class = (
                'success' if coverage_pct >= 80 else 
                'warning' if coverage_pct >= 60 else 
                'error'
            )
            functional_coverage_html.append(
                f'<div class="tablet:grid-col-4 margin-bottom-2">'
                f'<div class="usa-card">'
                f'<div class="usa-card__container">'
                f'<header class="usa-card__header">'
                f'<h3 class="usa-card__heading">{feature}</h3>'
                f'</header>'
                f'<div class="usa-card__body">'
                f'<span class="metric-value {status_class}">{coverage_pct:.1f}%</span>'
                f'<p>Scenarios: {details.get("scenarios_total", 0)}<br>'
                f'Automated: {details.get("scenarios_automated", 0)}</p>'
                f'</div></div></div></div>'
            )
        functional_coverage_html.append('</div>')
    else:
        functional_coverage_html.append(
            '<div class="usa-alert usa-alert--info" role="status">'
            '<div class="usa-alert__body">'
            '<p class="usa-alert__text">No functional coverage data available</p>'
            '</div></div>'
        )
    summary["functional_coverage_html"] = "".join(functional_coverage_html)

    # Generate test gaps HTML
    test_gaps_html = []
    if data["gaps"] and len(data["gaps"]) > 0:
        test_gaps_html.append('<ul class="usa-list">')
        for module in data["gaps"]:
            test_gaps_html.append(f'<li class="font-mono-sm">{module}</li>')
        test_gaps_html.append('</ul>')
    else:
        test_gaps_html.append(
            '<div class="usa-alert usa-alert--success" role="status">'
            '<div class="usa-alert__body">'
            '<p class="usa-alert__text">All modules have associated tests!</p>'
            '</div></div>'
        )
    summary["test_gaps_html"] = "".join(test_gaps_html)

    return summary

def generate_html_dashboard():
    """Generate HTML dashboard from all collected reports."""
    print("Generating HTML dashboard...")
    
    # Collect all report data
    data = collect_reports()
    
    # Directly construct the validation HTML to avoid double-escaping
    validation_checks_html = ""
    if data["validation"] and "validation_summary" in data["validation"] and "validation_checks" in data["validation"]["validation_summary"]:
        for check in data["validation"]["validation_summary"]["validation_checks"]:
            alert_class = "usa-alert--success" if check["passed"] else "usa-alert--error"
            icon = "✓" if check["passed"] else "✗"
            validation_checks_html += f"""
                <div class="usa-alert {alert_class} margin-bottom-2" role="status">
                    <div class="usa-alert__body">
                        <p class="usa-alert__text">{icon} {check["message"]}</p>
                    </div>
                </div>
            """
    else:
        validation_checks_html += """
            <div class="usa-alert usa-alert--info" role="status">
                <div class="usa-alert__body">
                    <p class="usa-alert__text">No validation data available</p>
                </div>
            </div>
        """
    
    # Directly construct the module coverage HTML
    module_coverage_html = ""
    if data["coverage"] and "files" in data["coverage"]:
        # Sort files by coverage
        sorted_files = sorted(
            [(path, info) for path, info in data["coverage"]["files"].items()],
            key=lambda x: x[1]["summary"]["percent_covered"]
        )
        
        if sorted_files:
            for file_path, file_data in sorted_files:
                module_name = file_path.replace("/", ".")
                coverage = file_data["summary"]["percent_covered"]
                missing_lines = len(file_data.get("missing_lines", []))
                
                status_class = (
                    'success' if coverage >= 80 else 
                    'warning' if coverage >= 60 else 
                    'error'
                )
                
                module_coverage_html += f"""
                    <tr>
                        <th scope="row" class="font-mono-sm">{module_name}</th>
                        <td class="text-center">
                            <span class="usa-tag usa-tag--big metric-value {status_class}" style="font-size: 1rem">
                            {coverage:.1f}%
                            </span>
                        </td>
                        <td class="text-right font-mono-sm">{missing_lines}</td>
                    </tr>
                """
        else:
            module_coverage_html += """
                <tr>
                    <td colspan="3" class="text-center">No source files found with coverage data</td>
                </tr>
            """
    else:
        module_coverage_html += """
            <tr>
                <td colspan="3" class="text-center">No coverage data available</td>
            </tr>
        """
    
    # Set up Jinja2 environment with autoescape turned OFF for this specific template
    env = Environment(
        loader=FileSystemLoader('docs/templates'),
        autoescape=False  # Turn off autoescaping to prevent double-escaping
    )
    
    # Prepare template data with the direct HTML strings
    template_data = {
        "generation_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_coverage": f"{data['coverage'].get('totals', {}).get('percent_covered', 0):.1f}",
        "coverage_status_class": 'success' if float(data['coverage'].get('totals', {}).get('percent_covered', 0)) >= 70 else 'error',
        "test_quality_score": f"{data['quality'].get('overall_quality_score', 0):.1f}",
        "quality_status_class": 'success' if float(data['quality'].get('overall_quality_score', 0)) >= 60 else 'error',
        "modules_without_tests": len(data.get("gaps", [])),
        "gaps_status_class": 'success' if len(data.get("gaps", [])) == 0 else 'error',
        "validation_passed": data.get("validation", {}).get("validation_summary", {}).get("passed", False),
        "validation_status_class": 'success' if data.get("validation", {}).get("validation_summary", {}).get("passed", False) else 'error',
        "validation_status_icon": '✓' if data.get("validation", {}).get("validation_summary", {}).get("passed", False) else '✗',
        "chart_data": json.dumps({"dates": data.get("history", {}).get("dates", []), "coverage": data.get("history", {}).get("coverage", [])}),
        
        # Add our directly constructed HTML
        "validation_checks_html": validation_checks_html,
        "module_coverage_html": module_coverage_html
    }
    
    # Load and render template
    template = env.get_template('test_coverage_dashboard.html')
    html = template.render(**template_data)
    
    # Write HTML to file, ensuring no escaping happens
    output_path = "output/reports/test_coverage_dashboard.html"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding='utf-8') as f:
        f.write(html)
    
    print(f"Dashboard generated at {output_path}")
    return output_path

if __name__ == "__main__":
    print("Analyzing test coverage...")
    
    # Run all analyses if they weren't already run
    if not os.path.exists("output/reports/coverage/coverage.json"):
        run_coverage_analysis()
    
    # Generate dashboard
    dashboard_path = generate_html_dashboard()
    
    print(f"Dashboard available at: {dashboard_path}")