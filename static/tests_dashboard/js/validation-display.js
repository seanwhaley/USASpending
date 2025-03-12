// Validation results display functionality
function displayValidationResults(data) {
    const container = document.getElementById('validation-results-section');
    if (!container) return;

    const validationSummary = data.validation_summary;
    const totalChecks = validationSummary.total_checks;
    const passedChecks = validationSummary.passed_checks;
    const failedChecks = validationSummary.failed_checks;

    container.innerHTML = `
        <section class="usa-section padding-y-2">
            <h2>Validation Results</h2>
            <div class="grid-row grid-gap">
                <div class="tablet:grid-col">
                    <div class="usa-summary-box" role="region" aria-labelledby="summary-box-key-info">
                        <div class="usa-summary-box__body">
                            <h3 class="usa-summary-box__heading">Summary</h3>
                            <div class="usa-summary-box__text">
                                <ul class="usa-list usa-list--unstyled">
                                    <li>Total Checks: ${totalChecks}</li>
                                    <li>Passed: ${passedChecks}</li>
                                    <li>Failed: ${failedChecks}</li>
                                </ul>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="tablet:grid-col">
                    <div class="validation-details">
                        ${validationSummary.validation_checks.map(check => `
                            <div class="usa-alert usa-alert--${check.passed ? 'success' : 'error'}" role="alert">
                                <div class="usa-alert__body">
                                    <p class="usa-alert__text">${check.message}</p>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            </div>
        </section>
    `;
}