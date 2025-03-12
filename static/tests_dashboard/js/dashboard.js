// Main dashboard initialization and coordination
document.addEventListener('DOMContentLoaded', () => {
    // Show section availability based on config
    function updateSectionAvailability() {
        const missingReports = [];
        for (const [report, available] of Object.entries(CONFIG.availableReports)) {
            if (!available) {
                missingReports.push(report);
                const section = document.getElementById(`${report}-section`);
                if (section) {
                    section.innerHTML = `
                        <div class="usa-alert usa-alert--info">
                            <div class="usa-alert__body">
                                <p class="usa-alert__text">
                                    ${report} data is not available. Run without --skip-${report} to see this section.
                                </p>
                            </div>
                        </div>
                    `;
                }
            }
        }

        if (missingReports.length > 0) {
            document.getElementById('data-source-info').innerHTML += `
                <br><small class="usa-alert__text--info">Some reports were skipped: ${missingReports.join(', ')}</small>
            `;
        }
    }

    // Initialize coverage summary section
    function initializeCoverageSummary(data) {
        if (!data.coverage) return;
        
        const summarySection = document.getElementById('coverage-summary-section');
        if (!summarySection) return;

        const coverage = data.coverage.coverage_percent || 0;
        const statusClass = coverage >= 80 ? 'success' : coverage >= 60 ? 'warning' : 'error';

        summarySection.innerHTML = `
            <section class="usa-section padding-y-2">
                <h2>Coverage Summary</h2>
                <div class="grid-row grid-gap">
                    <div class="tablet:grid-col">
                        <div class="usa-card">
                            <div class="usa-card__container">
                                <div class="usa-card__body">
                                    <h3>Overall Coverage</h3>
                                    <div class="metric-value ${statusClass}">${coverage.toFixed(1)}%</div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="tablet:grid-col">
                        <div class="usa-card">
                            <div class="usa-card__container">
                                <div class="usa-card__body">
                                    <h3>Files Analyzed</h3>
                                    <div class="metric-value">${data.coverage.total_files || 0}</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div id="coverage-trend-container" class="margin-top-4">
                    <canvas id="coverage-trend"></canvas>
                </div>
            </section>
        `;

        // Initialize coverage trend chart if data exists
        if (data.history && typeof createCoverageChart === 'function') {
            createCoverageChart('coverage-trend', data.history);
        }
    }

    // Initialize test gaps section
    function initializeTestGaps(data) {
        if (!data.gaps) return;

        const gapsSection = document.getElementById('test-gaps-section');
        if (!gapsSection) return;

        const gaps = data.gaps.gaps || [];
        gapsSection.innerHTML = `
            <section class="usa-section padding-y-2">
                <h2>Test Coverage Gaps</h2>
                ${gaps.length === 0 ? 
                    '<div class="usa-alert usa-alert--success"><div class="usa-alert__body"><p class="usa-alert__text">No test coverage gaps found!</p></div></div>' :
                    `<div class="usa-alert usa-alert--warning">
                        <div class="usa-alert__body">
                            <h4 class="usa-alert__heading">${gaps.length} files need test coverage</h4>
                            <ul class="usa-list">
                                ${gaps.map(gap => `<li>${gap}</li>`).join('')}
                            </ul>
                        </div>
                    </div>`
                }
            </section>
        `;
    }

    // Initialize functional coverage section
    function initializeFunctionalCoverage(data) {
        if (!data.functional) return;

        const functionalSection = document.getElementById('functional-coverage-section');
        if (!functionalSection) return;

        const coverage = data.functional.functional_coverage * 100 || 0;
        const statusClass = coverage >= 80 ? 'success' : coverage >= 60 ? 'warning' : 'error';

        functionalSection.innerHTML = `
            <section class="usa-section padding-y-2">
                <h2>Functional Coverage</h2>
                <div class="grid-row grid-gap">
                    <div class="tablet:grid-col">
                        <div class="usa-card">
                            <div class="usa-card__container">
                                <div class="usa-card__body">
                                    <h3>Function Coverage</h3>
                                    <div class="metric-value ${statusClass}">${coverage.toFixed(1)}%</div>
                                    <p>of ${data.functional.total_functions} total functions</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </section>
        `;
    }

    // Initialize validation section
    function initializeValidation(data) {
        if (!data.validation || typeof displayValidationResults !== 'function') return;
        displayValidationResults(data.validation);
    }

    // Listen for data loaded event
    document.addEventListener('dashboardDataLoaded', (event) => {
        const data = event.detail;
        
        // Update section availability first
        updateSectionAvailability();
        
        // Initialize each section if data is available
        if (CONFIG.availableReports.coverage) {
            initializeCoverageSummary(data);
        }
        if (CONFIG.availableReports.gaps) {
            initializeTestGaps(data);
        }
        if (CONFIG.availableReports.functional) {
            initializeFunctionalCoverage(data);
        }
        if (CONFIG.availableReports.validation) {
            initializeValidation(data);
        }
        
        // Show the dashboard content
        document.querySelector('.loading').style.display = 'none';
        document.querySelector('.dashboard-content').style.display = 'block';
    });

    // Start loading the dashboard data
    loadDashboardData();
});
