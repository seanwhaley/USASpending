// Data loader for the test coverage dashboard

// Dashboard data container
const dashboardData = {
    coverage: null,
    quality: null,
    gaps: null,
    validation: null,
    functional: null,
    history: null
};

// Debug info container
const debugInfo = {
    loadStartTime: null,
    loadEndTime: null,
    fileStatuses: {},
    isSampleData: false
};

// Utility function to log debug information
function logDebug(message) {
    const debugContainer = document.getElementById('debug-container');
    if (!debugContainer) return;
    
    const timestamp = new Date().toLocaleTimeString();
    const logEntry = document.createElement('div');
    logEntry.textContent = `[${timestamp}] ${message}`;
    debugContainer.appendChild(logEntry);
    console.log(`[DEBUG] ${message}`);
}

// Utility function to fetch JSON data with error handling
async function fetchJSON(url, label) {
    logDebug(`Fetching ${label} from ${url}`);
    debugInfo.fileStatuses[label] = 'Fetching...';
    
    try {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP error ${response.status}`);
        }
        
        const data = await response.json();
        debugInfo.fileStatuses[label] = 'Success';
        logDebug(`Successfully loaded ${label}`);
        
        return data;
    } catch (error) {
        debugInfo.fileStatuses[label] = `Error: ${error.message}`;
        logDebug(`Error fetching ${label}: ${error.message}`);
        return null;
    }
}

// Sample data detection
function checkForSampleData() {
    // Check for patterns that would indicate sample data
    const sampleDataSignatures = [
        // History dates in the future
        () => {
            if (dashboardData.history && Array.isArray(dashboardData.history.dates)) {
                const futureDates = dashboardData.history.dates.filter(date => {
                    const dateObj = new Date(date);
                    return dateObj > new Date();
                });
                return futureDates.length > 0;
            }
            return false;
        },
        // Standard modules from sample data
        () => {
            if (dashboardData.coverage && dashboardData.coverage.files) {
                const sampleModulePaths = [
                    "src/usaspending/adapters/base.py",
                    "src/usaspending/adapters/boolean_adapters.py",
                    "src/usaspending/entities/entity_mapper.py"
                ];
                return sampleModulePaths.some(path => path in dashboardData.coverage.files);
            }
            return false;
        },
        // Exact coverage values from sample data
        () => {
            if (dashboardData.coverage && dashboardData.coverage.totals) {
                return dashboardData.coverage.totals.percent_covered === 75.8;
            }
            return false;
        },
    ];

    // Check each signature
    for (const check of sampleDataSignatures) {
        if (check()) {
            logDebug("Sample data detected");
            debugInfo.isSampleData = true;
            return true;
        }
    }

    logDebug("No sample data detected - assuming real test results");
    return false;
}

// Load all required data files
async function loadDashboardData() {
    logDebug('Starting data load process');
    debugInfo.loadStartTime = new Date();
    
    // Use the config file that was auto-generated
    if (typeof CONFIG === 'undefined') {
        logDebug('ERROR: Config file not loaded. Dashboard cannot continue.');
        showError('Configuration Error', 'The dashboard configuration could not be loaded.');
        return;
    }
    
    // List of files to load from CONFIG.dataPaths
    const filesToLoad = Object.entries(CONFIG.dataPaths).map(([name, path]) => ({
        name,
        path
    }));
    
    // Load each file
    for (const file of filesToLoad) {
        const url = file.path;
        const data = await fetchJSON(url, file.name);
        
        if (data) {
            dashboardData[file.name] = data;
            logDebug(`Successfully loaded ${file.name} from ${url}`);
        } else {
            logDebug(`Failed to load ${file.name} from ${url}`);
        }
    }
    
    debugInfo.loadEndTime = new Date();
    logDebug(`Data loading completed in ${debugInfo.loadEndTime - debugInfo.loadStartTime}ms`);
    
    // Check if we're using sample data
    checkForSampleData();
    if (debugInfo.isSampleData) {
        document.getElementById('sample-data-banner').style.display = 'block';
        document.getElementById('data-source-info').innerHTML = '<strong class="usa-alert__text--warning">⚠️ SAMPLE DATA</strong> - This dashboard is displaying example data, not actual test results';
    } else {
        document.getElementById('data-source-info').textContent = 'Using actual test results from the latest test run';
    }
    
    // Display data load error if no data was loaded
    const hasAnyData = Object.values(dashboardData).some(value => value !== null);
    if (!hasAnyData) {
        showError('Data Loading Error', 'No data could be loaded for the dashboard. Please check that the coverage reports exist.');
        return;
    }
    
    // Continue with rendering
    document.dispatchEvent(new CustomEvent('dashboardDataLoaded', { detail: dashboardData }));
}

// Show error message
function showError(title, message) {
    const container = document.getElementById('dashboard-container');
    if (!container) return;
    
    container.innerHTML = `
        <div class="usa-alert usa-alert--error" role="alert">
            <div class="usa-alert__body">
                <h4 class="usa-alert__heading">${title}</h4>
                <p class="usa-alert__text">${message}</p>
                <button id="show-debug-btn" class="usa-button">Show Technical Details</button>
            </div>
        </div>
        <div id="tech-debug-info" class="debug-info" style="display: none;"></div>
    `;
    
    // Add event listener for the debug button
    document.getElementById('show-debug-btn').addEventListener('click', function() {
        const debugElem = document.getElementById('tech-debug-info');
        debugElem.style.display = 'block';
        debugElem.innerHTML = `<h4>File Status:</h4>
            <pre>${JSON.stringify(debugInfo.fileStatuses, null, 2)}</pre>`;
    });
}

// Utility function to determine status class based on value and thresholds
function getStatusClass(value, goodThreshold = 80, warningThreshold = 60) {
    if (value >= goodThreshold) return 'success';
    if (value >= warningThreshold) return 'warning';
    return 'error';
}

// Export functions for other modules
window.dashboardUtils = {
    dashboardData,
    debugInfo,
    getStatusClass,
    logDebug
};

// Data loading and initialization
class DashboardDataLoader {
    constructor() {
        this.data = {};
        this.loadingPromises = [];
        this.debugLog = [];
    }

    async init() {
        this.log('Initializing dashboard data loader');
        
        try {
            await this.loadAllData();
            this.showContent();
            this.updateGenerationTime();
            this.hideLoadingIndicator();
        } catch (error) {
            this.log('Error loading dashboard data:', error);
            this.showError('Failed to load dashboard data. Check console for details.');
        }
    }

    async loadAllData() {
        const dataPaths = CONFIG.dataPaths;
        
        // Load all data files
        await Promise.all([
            this.loadJSON(dataPaths.coverage, 'coverage'),
            this.loadJSON(dataPaths.quality, 'quality'),
            this.loadJSON(dataPaths.gaps, 'gaps'),
            this.loadJSON(dataPaths.validation, 'validation'),
            this.loadJSON(dataPaths.history, 'history')
        ]);
    }

    async loadJSON(path, key) {
        this.log(`Loading ${key} data from ${path}`);
        try {
            const response = await fetch(path);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            this.data[key] = await response.json();
            this.log(`Successfully loaded ${key} data`);
        } catch (error) {
            this.log(`Error loading ${key} data:`, error);
            this.data[key] = null;
        }
    }

    hideLoadingIndicator() {
        const container = document.getElementById('dashboard-container');
        if (container) {
            container.classList.add('loaded');
        }
    }

    showContent() {
        const content = document.querySelector('.dashboard-content');
        if (content) {
            content.style.display = 'block';
        }
    }

    updateGenerationTime() {
        const timeElement = document.getElementById('generation-time');
        if (timeElement && CONFIG.generatedAt) {
            const date = new Date(CONFIG.generatedAt);
            timeElement.textContent = date.toLocaleString();
        }
    }

    showError(message) {
        const container = document.getElementById('dashboard-container');
        if (container) {
            container.innerHTML = `
                <div class="usa-alert usa-alert--error" role="alert">
                    <div class="usa-alert__body">
                        <h4 class="usa-alert__heading">Error</h4>
                        <p class="usa-alert__text">${message}</p>
                    </div>
                </div>
            `;
        }
    }

    log(...args) {
        const message = args.map(arg => 
            typeof arg === 'object' ? JSON.stringify(arg) : arg
        ).join(' ');
        this.debugLog.push(`${new Date().toISOString()} - ${message}`);
        console.log(...args);
    }

    setupDebugPanel() {
        const toggleButton = document.getElementById('toggle-debug');
        const debugContainer = document.getElementById('debug-container');
        
        if (toggleButton && debugContainer) {
            toggleButton.addEventListener('click', () => {
                const isHidden = debugContainer.style.display === 'none';
                debugContainer.style.display = isHidden ? 'block' : 'none';
                toggleButton.textContent = isHidden ? 'Hide Loading Details' : 'Show Loading Details';
                
                if (isHidden) {
                    debugContainer.innerHTML = this.debugLog.join('\n');
                }
            });
        }
    }
}

// Initialize dashboard when window loads
window.addEventListener('load', () => {
    window.dashboardData = new DashboardDataLoader();
    window.dashboardData.init().then(() => {
        window.dashboardData.setupDebugPanel();
        
        // Initialize charts and displays if their functions exist
        if (typeof createCoverageChart === 'function' && window.dashboardData.data.history) {
            createCoverageChart('coverage-trend', window.dashboardData.data.history);
        }
        
        if (typeof displayValidationResults === 'function' && window.dashboardData.data.validation) {
            displayValidationResults(window.dashboardData.data.validation);
        }
    });
});
