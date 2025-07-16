// Global variables
let processedFiles = [];
let totalRecords = 0;
let authToken = null;
let currentUser = null;
let selectedFiles = [];
let processedResults = [];
let rawExtractions = [];
let structuredRecords = [];

// Initialize page
document.addEventListener('DOMContentLoaded', function () {
    console.log("DOM content loaded, initializing page");

    // Check for token in URL (after OAuth redirect)
    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token');

    if (token) {
        // Store token and remove from URL
        storeToken(token);
        window.history.replaceState({}, document.title, '/');
    }

    // Check if we're on the login page
    const isLoginPage = window.location.pathname.includes('/login');

    // Only check auth if not on login page
    if (!isLoginPage) {
        // Check if user is logged in
        checkAuth().then((isAuthenticated) => {
            if (isAuthenticated) {
                // User is authenticated, initialize the app
                console.log("User is authenticated, initializing app");
                initializeApp();
            } else {
                // User is not authenticated, redirect to login page
                console.log("User is not authenticated, redirecting to login");
                window.location.href = '/login';
            }
        });
    }
});

function storeToken(token) {
    // Store token in localStorage
    localStorage.setItem('auth_token', token);
    authToken = token;
}

function getToken() {
    // Get token from localStorage if not already loaded
    if (!authToken) {
        authToken = localStorage.getItem('auth_token');
    }
    return authToken;
}

function clearToken() {
    // Clear token from localStorage
    localStorage.removeItem('auth_token');
    authToken = null;
    currentUser = null;
}

async function checkAuth() {
    // Check if user is authenticated
    const token = getToken();
    if (!token) {
        return false;
    }

    try {
        // Try to get user info
        const response = await fetch('/auth/me', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (response.ok) {
            // Store user info
            currentUser = await response.json();
            return true;
        } else {
            // Clear invalid token
            clearToken();
            return false;
        }
    } catch (error) {
        console.error('Error checking authentication:', error);
        clearToken();
        return false;
    }
}

function initializeApp() {
    // Set up the file upload functionality
    setupFileUpload();

    // Set up the export options
    setupExportOptions();

    // Load header configurations
    loadHeaderConfigurations();

    // Check session status to load any existing data
    checkSessionStatus();
}

// Load header configurations
async function loadHeaderConfigurations() {
    try {
        const token = getToken();
        const response = await fetch('/api/header-config/', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (response.ok) {
            const configs = await response.json();
            const dropdown = document.getElementById('header-config-dropdown');

            // Clear existing options except the default
            while (dropdown.options.length > 1) {
                dropdown.remove(1);
            }

            // Add configurations to dropdown
            configs.forEach(config => {
                const option = document.createElement('option');
                option.value = config.id;
                option.textContent = config.name + (config.is_default ? ' (Default)' : '');
                dropdown.appendChild(option);

                // Select default configuration
                if (config.is_default) {
                    dropdown.value = config.id;
                }
            });
        } else {
            console.error('Failed to load header configurations');
        }
    } catch (error) {
        console.error('Error loading header configurations:', error);
    }
}

function setupFileUpload() {
    const dropArea = document.getElementById('drop-area');
    const fileInput = document.getElementById('file-input');
    const fileList = document.getElementById('file-list');
    const uploadButton = document.getElementById('upload-button');
    const clearButton = document.getElementById('clear-button');

    if (!dropArea || !fileInput || !fileList || !uploadButton || !clearButton) {
        console.error("Required file upload elements not found");
        return;
    }

    // Prevent default drag behaviors
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, preventDefaults, false);
        document.body.addEventListener(eventName, preventDefaults, false);
    });

    // Highlight drop area when item is dragged over it
    ['dragenter', 'dragover'].forEach(eventName => {
        dropArea.addEventListener(eventName, highlight, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, unhighlight, false);
    });

    // Handle dropped files
    dropArea.addEventListener('drop', handleDrop, false);

    // Handle file input change
    fileInput.addEventListener('change', handleFileInputChange);

    // Handle upload button click
    document.getElementById('upload-form').addEventListener('submit', function (e) {
        e.preventDefault();
        if (selectedFiles.length > 0) {
            uploadFiles(selectedFiles);
        }
    });

    // Handle clear button click
    clearButton.addEventListener('click', async function () {
        if (confirm('Are you sure you want to clear all data? This will remove all uploaded files and extracted data.')) {
            await clearAllData();
        } else {
            // Just clear the selected files without calling the backend
            clearSelectedFiles();
        }
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    function highlight() {
        dropArea.classList.add('highlight');
    }

    function unhighlight() {
        dropArea.classList.remove('highlight');
    }

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles(files);
    }

    function handleFileInputChange() {
        const files = fileInput.files;
        handleFiles(files);
    }

    function handleFiles(files) {
        if (files.length === 0) return;

        // Filter for PDF, image, and ZIP files
        const allowedTypes = [
            'application/pdf',
            'image/png',
            'image/jpeg',
            'image/webp',
            'application/zip'
        ];
        const allowedExtensions = ['.pdf', '.png', '.jpg', '.jpeg', '.webp', '.zip'];

        // Separate valid and invalid files
        const validFiles = [];
        const invalidFiles = [];

        Array.from(files).forEach(file => {
            const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
            if (allowedTypes.includes(file.type) || allowedExtensions.includes(fileExtension)) {
                validFiles.push(file);
            } else {
                invalidFiles.push(file);
            }
        });

        // Show message if there are invalid files
        if (invalidFiles.length > 0) {
            const invalidFileNames = invalidFiles.map(f => f.name).join(', ');
            showStatusMessage(`Unsupported file type(s): ${invalidFileNames}. Only PDF, PNG, JPG, JPEG, WebP, and ZIP files are supported.`, 'error');
        }

        if (validFiles.length === 0) {
            return;
        }

        // Add to selected files
        selectedFiles = [...selectedFiles, ...validFiles];

        // Update UI
        updateFileList();

        // Show count of selected files
        const fileCount = selectedFiles.length;
        const fileWord = fileCount === 1 ? 'file' : 'files';
        showStatusMessage(`${fileCount} ${fileWord} selected and ready to upload`, 'info');

        // Enable upload and clear buttons
        uploadButton.disabled = false;
        clearButton.disabled = false;
    }

    function updateFileList() {
        fileList.innerHTML = '';

        // Show file count if many files
        if (selectedFiles.length > 10) {
            const fileCountHeader = document.createElement('div');
            fileCountHeader.className = 'file-count-header';
            fileCountHeader.innerHTML = `<span>${selectedFiles.length} files selected</span> <small>(showing first 10)</small>`;
            fileList.appendChild(fileCountHeader);
        }

        // Show files (limit to first 10 if there are many)
        const filesToShow = selectedFiles.length > 10 ? selectedFiles.slice(0, 10) : selectedFiles;

        filesToShow.forEach((file, index) => {
            const fileItem = document.createElement('div');
            fileItem.className = 'file-item';

            const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
            const fileIcon = file.type === 'application/pdf' || fileExtension === '.pdf' ? 'fa-file-pdf' :
                file.type === 'image/png' || fileExtension === '.png' ? 'fa-file-image' :
                    file.type === 'image/jpeg' || fileExtension === '.jpg' || fileExtension === '.jpeg' ? 'fa-file-image' :
                        file.type === 'image/webp' || fileExtension === '.webp' ? 'fa-file-image' :
                            file.type === 'application/zip' || fileExtension === '.zip' ? 'fa-file-archive' : 'fa-file';

            fileItem.innerHTML = `
                <div class="file-name">
                    <i class="fas ${fileIcon}"></i>
                    ${file.name} (${formatFileSize(file.size)})
                </div>
                <button type="button" class="file-remove" data-index="${index}">
                    <i class="fas fa-times"></i>
                </button>
            `;

            fileList.appendChild(fileItem);

            // Add event listener to remove button
            fileItem.querySelector('.file-remove').addEventListener('click', function () {
                const index = parseInt(this.getAttribute('data-index'));
                selectedFiles.splice(index, 1);
                updateFileList();

                if (selectedFiles.length === 0) {
                    uploadButton.disabled = true;
                    clearButton.disabled = true;
                    showStatusMessage('No files uploaded yet', 'info');
                } else {
                    const fileCount = selectedFiles.length;
                    const fileWord = fileCount === 1 ? 'file' : 'files';
                    showStatusMessage(`${fileCount} ${fileWord} selected and ready to upload`, 'info');
                }
            });
        });

        // Show "more files" indicator if needed
        if (selectedFiles.length > 10) {
            const moreFiles = document.createElement('div');
            moreFiles.className = 'more-files';
            moreFiles.textContent = `+ ${selectedFiles.length - 10} more files`;
            fileList.appendChild(moreFiles);
        }
    }
}

// Global clearSelectedFiles function that can be called from anywhere
function clearSelectedFiles() {
    selectedFiles = [];
    const fileList = document.getElementById('file-list');
    const uploadButton = document.getElementById('upload-button');
    const clearButton = document.getElementById('clear-button');
    const fileInput = document.getElementById('file-input');

    if (fileList) fileList.innerHTML = '';
    if (uploadButton) uploadButton.disabled = true;
    if (clearButton) clearButton.disabled = true;
    if (fileInput) fileInput.value = '';
}

// Function to clear all data (call backend endpoint)
async function clearAllData() {
    showStatusMessage('Clearing all data...', 'info');
    showProgressBar(true);

    try {
        const token = getToken();
        const response = await fetch('/api/clear-session', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || `HTTP error! Status: ${response.status}`);
        }

        const result = await response.json();
        console.log("Clear session result:", result);

        // Clear selected files
        clearSelectedFiles();

        // Clear stored data
        rawExtractions = [];
        structuredRecords = [];

        // Update session status to refresh UI
        await updateSessionStatus();

        // Update extraction results display
        updateExtractionResults();

        const recordsDeleted = result.records_deleted || 0;
        showStatusMessage(`All data has been cleared successfully (${recordsDeleted} records deleted)`, 'success');
    } catch (error) {
        console.error('Error clearing data:', error);
        showStatusMessage(`Failed to clear data: ${error.message}`, 'error');
    } finally {
        showProgressBar(false);
    }
}

function setupExportOptions() {
    const exportFormat = document.getElementById('export-format');
    const dataTypeContainer = document.getElementById('data-type-container');
    const dataType = document.getElementById('data-type');
    const customHeader = document.getElementById('custom-header');
    const headerInputContainer = document.getElementById('header-input-container');
    const headerInput = document.getElementById('header-input');
    const downloadBtn = document.getElementById('download-btn');
    const driveBtn = document.getElementById('drive-btn');

    if (!exportFormat || !dataTypeContainer || !dataType || !customHeader ||
        !headerInputContainer || !headerInput || !downloadBtn || !driveBtn) {
        console.error("Required export option elements not found");
        return;
    }

    // Handle export format change
    exportFormat.addEventListener('change', function () {
        updateExportOptions();
    });

    // Handle data type change
    dataType.addEventListener('change', function () {
        updateHeaderVisibility();
    });

    // Handle custom header toggle
    customHeader.addEventListener('change', function () {
        headerInputContainer.style.display = this.checked ? 'block' : 'none';
    });

    // Handle download button click
    downloadBtn.addEventListener('click', function () {
        downloadExport();
    });

    // Handle drive button click
    driveBtn.addEventListener('click', function () {
        exportToDrive();
    });

    function updateExportOptions() {
        const format = exportFormat.value;

        // Show/hide data type selector for JSON format
        if (format === 'json') {
            dataTypeContainer.style.display = 'block';
        } else {
            dataTypeContainer.style.display = 'none';
        }

        updateHeaderVisibility();
    }

    function updateHeaderVisibility() {
        const format = exportFormat.value;
        const isRawData = dataType.value === 'raw';

        // Hide header config for JSON raw data
        if (format === 'json' && isRawData) {
            document.getElementById('header-config').style.display = 'none';
        } else {
            document.getElementById('header-config').style.display = 'block';
        }
    }
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';

    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));

    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

async function uploadFiles(files) {
    showProgressBar(true);
    showStatusMessage('Uploading and processing files...', 'info');

    try {
        const formData = new FormData();
        files.forEach(file => {
            formData.append('files', file);
        });

        // Add header configuration if selected
        const headerConfigId = document.getElementById('header-config-dropdown').value;
        if (headerConfigId) {
            formData.append('header_config_id', headerConfigId);
        }

        const token = getToken();

        const response = await fetch('/api/extract', {
            method: 'POST',
            body: formData,
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || `HTTP error! Status: ${response.status}`);
        }

        const data = await response.json();

        // Check for errors
        if (data.errors && data.errors.length > 0) {
            const errorMessages = data.errors.map(err =>
                `<li><strong>${err.filename}</strong>: ${err.error}</li>`
            ).join('');

            if (data.results && data.results.length > 0) {
                showStatusMessage(`Processed ${data.results.length} records with some errors: <ul>${errorMessages}</ul>`, 'warning');
            } else {
                showStatusMessage(`Failed to process files: <ul>${errorMessages}</ul>`, 'error');
            }
        } else {
            showStatusMessage(`Successfully processed ${data.results ? data.results.length : 0} records.`, 'success');
        }

        // Clear selected files after successful upload
        clearSelectedFiles();

        // Update session status to refresh data
        await updateSessionStatus();

        // Update extraction results display
        updateExtractionResults();
    } catch (error) {
        console.error('Error uploading files:', error);
        showStatusMessage(`Error: ${error.message}`, 'error');
    } finally {
        showProgressBar(false);
    }
}

function showProgressBar(show) {
    const progressContainer = document.getElementById('progress-container');
    const progressBar = document.getElementById('progress-bar');

    if (progressContainer) {
        progressContainer.style.display = show ? 'block' : 'none';

        if (show && progressBar) {
            // Animate the progress bar
            progressBar.style.width = '0%';
            setTimeout(() => {
                progressBar.style.width = '90%';
            }, 100);
        }
    }
}

function showStatusMessage(message, type = 'info') {
    const statusMessage = document.getElementById('status-message');
    if (statusMessage) {
        statusMessage.innerHTML = message;
        statusMessage.className = 'status-message';
        statusMessage.classList.add(type);
    }
}

async function updateSessionStatus() {
    try {
        console.log("Fetching session status...");
        const token = getToken();

        const response = await fetch('/api/session-status', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            throw new Error(`Server responded with status: ${response.status}`);
        }

        const status = await response.json();
        console.log("Session status:", status);

        // Store raw extractions and structured records for later use
        if (status.results) {
            rawExtractions = status.results.filter(result => result.is_raw_extraction);
            structuredRecords = status.results.filter(result => !result.is_raw_extraction);
        }

        // Enable/disable buttons based on available records
        const hasRecords = (status.total_records || 0) > 0;
        const downloadBtn = document.getElementById('download-btn');
        const driveBtn = document.getElementById('drive-btn');
        const clearBtn = document.getElementById('clear-button');

        if (downloadBtn) downloadBtn.disabled = !hasRecords;
        if (driveBtn) driveBtn.disabled = !hasRecords;
        if (clearBtn) clearBtn.disabled = !hasRecords;

        return status;
    } catch (error) {
        console.error('Error updating session status:', error);
        return null;
    }
}

function updateExtractionResults() {
    const extractionResults = document.getElementById('extraction-results');
    if (!extractionResults) return;

    if (structuredRecords.length === 0 && rawExtractions.length === 0) {
        extractionResults.innerHTML = '<div class="no-results">No extraction results available</div>';
        return;
    }

    let html = '';

    // Use structured records if available, otherwise use raw extractions
    const records = structuredRecords.length > 0 ? structuredRecords : rawExtractions;

    records.slice(0, 5).forEach(record => {
        html += `
            <div class="result-item">
                <div class="result-header">
                    <div class="result-title">${record.bank_name || 'Unknown Bank'}</div>
                </div>
                <div class="result-details">
                    <div class="result-field">
                        <div class="field-label">Account Number</div>
                        <div class="field-value">${record.account_number || 'N/A'}</div>
                    </div>
                    <div class="result-field">
                        <div class="field-label">Account Name</div>
                        <div class="field-value">${record.account_name || 'N/A'}</div>
                    </div>
                    <div class="result-field">
                        <div class="field-label">SWIFT/BIC</div>
                        <div class="field-value">${record.swift_code || 'N/A'}</div>
                    </div>
                    <div class="result-field">
                        <div class="field-label">IBAN</div>
                        <div class="field-value">${record.iban || 'N/A'}</div>
                    </div>
                </div>
            </div>
        `;
    });

    if (records.length > 5) {
        html += `<div class="more-results">+ ${records.length - 5} more records</div>`;
    }

    extractionResults.innerHTML = html;
}

async function checkSessionStatus() {
    try {
        const token = getToken();

        const response = await fetch('/api/session-status', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        const status = await response.json();

        // Store raw extractions and structured records
        if (status.results) {
            rawExtractions = status.results.filter(result => result.is_raw_extraction);
            structuredRecords = status.results.filter(result => !result.is_raw_extraction);
        }

        // Update extraction results display
        updateExtractionResults();

        // Enable/disable buttons
        const hasRecords = (status.total_records || 0) > 0;
        const downloadBtn = document.getElementById('download-btn');
        const driveBtn = document.getElementById('drive-btn');
        const clearBtn = document.getElementById('clear-button');

        if (downloadBtn) downloadBtn.disabled = !hasRecords;
        if (driveBtn) driveBtn.disabled = !hasRecords;
        if (clearBtn) clearBtn.disabled = !hasRecords;

        if (hasRecords) {
            showStatusMessage(`${status.total_records} records available for export`, 'success');
        }
    } catch (error) {
        console.error('Error checking session status:', error);
        showStatusMessage('Error loading session data', 'error');
    }
}

function downloadExport() {
    const format = document.getElementById('export-format').value;
    const isRawData = document.getElementById('data-type').value === 'raw';
    const useCustomHeader = document.getElementById('custom-header').checked;
    const customHeaders = useCustomHeader ? document.getElementById('header-input').value : '';

    // Get selected header configuration
    const headerConfigId = document.getElementById('header-config-dropdown').value;

    let url = '';

    if (format === 'json') {
        url = `/api/download-json?use_raw=${isRawData}`;
    } else {
        url = `/api/download-csv?format=${format}&use_raw=${isRawData}`;

        if (headerConfigId) {
            url += `&config_id=${headerConfigId}`;
        } else if (useCustomHeader && customHeaders) {
            url += `&custom_headers=${encodeURIComponent(customHeaders)}`;
        }
    }

    // Add auth token to URL
    const token = getToken();
    if (token) {
        url += `&token=${encodeURIComponent(token)}`;
    }

    // Trigger download
    window.location.href = url;
}

async function exportToDrive() {
    showProgressBar(true);
    showStatusMessage('Exporting to Google Drive...', 'info');

    try {
        const format = document.getElementById('export-format').value;
        const isRawData = document.getElementById('data-type').value === 'raw';
        const useCustomHeader = document.getElementById('custom-header').checked;
        const customHeaders = useCustomHeader ? document.getElementById('header-input').value : '';

        // Get selected header configuration
        const headerConfigId = document.getElementById('header-config-dropdown').value;

        // Generate filename with timestamp
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        const fileName = `bank_details_${timestamp}.${format === 'json' ? 'json' : format}`;

        const token = getToken();

        const response = await fetch('/drive/export', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                file_name: fileName,
                format: format,
                use_raw: isRawData,
                config_id: headerConfigId || undefined,
                custom_headers: useCustomHeader && !headerConfigId ? customHeaders : null
            })
        });

        if (!response.ok) {
            const errorData = await response.json();

            // Check if it's an authorization error
            if (response.status === 401 && errorData.detail === "Google Drive authorization required") {
                // Redirect to authorization URL
                window.location.href = '/drive/auth';
                return;
            }

            throw new Error(errorData.detail || 'Failed to export to Google Drive');
        }

        const result = await response.json();

        showStatusMessage(`
            <div class="success-message">
                <p>Successfully exported to Google Drive!</p>
                <p><a href="${result.link}" target="_blank" class="drive-link">
                    <i class="fab fa-google-drive"></i> View File in Google Drive
                </a></p>
            </div>
        `, 'success');
    } catch (error) {
        console.error('Error exporting to Google Drive:', error);
        showStatusMessage(`Error exporting to Google Drive: ${error.message}`, 'error');
    } finally {
        showProgressBar(false);
    }
} 