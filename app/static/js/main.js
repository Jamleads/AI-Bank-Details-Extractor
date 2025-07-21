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

            // Check if user is disabled (status is inactive)
            if (currentUser.status === 'inactive') {
                // Redirect to disabled page
                window.location.href = '/disabled';
                return false;
            }

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

    // Enable clear button
    const clearBtn = document.getElementById('clear-button');
    if (clearBtn) clearBtn.disabled = false;

    // Check session status to load any existing data
    checkSessionStatus();

    // Check Drive auth status
    checkDriveAuthStatus();
}

// Add this function to the file
function checkDriveAuthStatus() {
    const urlParams = new URLSearchParams(window.location.search);

    // Check for Drive auth success
    if (urlParams.has('drive_auth') && urlParams.get('drive_auth') === 'success') {
        showStatusMessage(`
            <div class="success-message">
                <p>Successfully connected to Google Drive!</p>
                <p>You can now export your data to Google Drive.</p>
            </div>
        `, 'success');
    }

    // Check for Drive auth errors
    if (urlParams.has('error')) {
        const error = urlParams.get('error');
        const message = urlParams.get('message') || 'Unknown error';

        let errorMessage = 'Error connecting to Google Drive: ';

        switch (error) {
            case 'missing_user_id':
                errorMessage += 'User session expired. Please try again.';
                break;
            case 'invalid_state':
                errorMessage += 'Authentication state mismatch. Please try again.';
                break;
            case 'auth_error':
                errorMessage += `Authentication failed: ${message}`;
                break;
            case 'storage_error':
                errorMessage += `Failed to store credentials: ${message}`;
                break;
            default:
                errorMessage += message;
        }

        showStatusMessage(errorMessage, 'error');
    }

    // Clean up URL parameters
    if (urlParams.has('drive_auth') || urlParams.has('error')) {
        // Remove query parameters without refreshing the page
        const newUrl = window.location.pathname;
        window.history.replaceState({}, document.title, newUrl);
    }
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

            // Get both dropdowns
            const exportDropdown = document.getElementById('header-config-dropdown');
            const uploadDropdown = document.getElementById('upload-header-config');

            // Clear existing options in export dropdown
            if (exportDropdown) {
                while (exportDropdown.options.length > 1) {
                    exportDropdown.remove(1);
                }
            }

            // Clear existing options in upload dropdown
            if (uploadDropdown) {
                while (uploadDropdown.options.length > 1) {
                    uploadDropdown.remove(1);
                }
            }

            // Add configurations to both dropdowns
            configs.forEach(config => {
                // For export dropdown
                if (exportDropdown) {
                    const exportOption = document.createElement('option');
                    exportOption.value = config.id;
                    exportOption.textContent = config.name + (config.is_default ? ' (Default)' : '');
                    exportDropdown.appendChild(exportOption);

                    // Select default configuration
                    if (config.is_default) {
                        exportDropdown.value = config.id;
                    }
                }

                // For upload dropdown
                if (uploadDropdown) {
                    const uploadOption = document.createElement('option');
                    uploadOption.value = config.id;
                    uploadOption.textContent = config.name + (config.is_default ? ' (Default)' : '');
                    uploadDropdown.appendChild(uploadOption);

                    // Select default configuration
                    if (config.is_default) {
                        uploadDropdown.value = config.id;
                    }
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
    // Get DOM elements
    const fileInput = document.getElementById('fileInput');
    const dropArea = document.getElementById('uploadArea');
    const fileList = document.getElementById('fileList');
    const uploadButton = document.getElementById('processBtn');
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
    uploadButton.addEventListener('click', function (e) {
        e.preventDefault();
        if (selectedFiles.length > 0) {
            uploadFiles(selectedFiles);
        }
    });

    // NOTE: Clear button event listener is now handled in index.html to avoid duplicate handlers
    // clearButton.addEventListener('click', async function () {
    //     if (confirm('Are you sure you want to clear all data? This will remove all uploaded files and extracted data.')) {
    //         await clearAllData();
    //     } else {
    //         // Just clear the selected files without calling the backend
    //         clearSelectedFiles();
    //     }
    // });

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
    const fileList = document.getElementById('fileList');
    const uploadButton = document.getElementById('processBtn');
    const clearButton = document.getElementById('clear-button');
    const fileInput = document.getElementById('fileInput');

    if (fileList) fileList.innerHTML = '';
    if (uploadButton) uploadButton.disabled = true;
    if (clearButton) clearButton.disabled = true;
    if (fileInput) fileInput.value = '';
}

// Function to clear all data (call backend endpoint)
async function clearAllData() {
    // This function is kept for reference but is no longer used directly
    // The clear button event handler is now implemented in index.html

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

        return result;
    } catch (error) {
        console.error('Error clearing data:', error);
        showStatusMessage(`Failed to clear data: ${error.message}`, 'error');
        throw error; // Re-throw the error so the caller can handle it
    } finally {
        showProgressBar(false);
    }
}

function setupExportOptions() {
    const exportFormat = document.getElementById('export-format');
    const downloadBtn = document.getElementById('download-btn');
    const driveBtn = document.getElementById('drive-btn');

    if (!exportFormat || !downloadBtn || !driveBtn) {
        console.error("Required export option elements not found");
        return;
    }

    // Handle export format change
    exportFormat.addEventListener('change', function () {
        updateExportOptions();
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
        // Any format-specific options can be handled here
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
        const headerConfigId = document.getElementById('upload-header-config').value;
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

        // Always enable the clear button
        if (clearBtn) clearBtn.disabled = false;

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

        // Always enable the clear button
        if (clearBtn) clearBtn.disabled = false;

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

    // Get selected header configuration
    const headerConfigId = document.getElementById('header-config-dropdown').value;

    let url = '';

    if (format === 'json') {
        url = `/api/download-json`;
    } else {
        url = `/api/download-csv?format=${format}`;

        if (headerConfigId) {
            url += `&config_id=${headerConfigId}`;
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
                config_id: headerConfigId || undefined
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
                <p><i class="fas fa-check-circle"></i> Successfully exported to Google Drive!</p>
                <div class="drive-link-container">
                    <p>File: <strong>${fileName}</strong></p>
                    <a href="${result.link}" target="_blank" class="drive-link-button">
                        <i class="fab fa-google-drive"></i> View File in Google Drive
                    </a>
                </div>
            </div>
        `, 'success');

        // Add some CSS for the drive link button
        const style = document.createElement('style');
        style.textContent = `
            .drive-link-container {
                margin-top: 10px;
                padding: 10px;
                background-color: #f8f9fa;
                border-radius: 5px;
                border-left: 4px solid #4285F4;
            }
            .drive-link-button {
                display: inline-block;
                margin-top: 5px;
                padding: 8px 16px;
                background-color: #4285F4;
                color: white !important;
                border-radius: 4px;
                text-decoration: none;
                font-weight: bold;
                transition: background-color 0.3s;
            }
            .drive-link-button:hover {
                background-color: #3367D6;
                text-decoration: none;
            }
        `;
        document.head.appendChild(style);
    } catch (error) {
        console.error('Error exporting to Google Drive:', error);
        showStatusMessage(`Error exporting to Google Drive: ${error.message}`, 'error');
    } finally {
        showProgressBar(false);
    }
} 