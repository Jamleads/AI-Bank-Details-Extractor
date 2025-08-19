// Global variables
let processedFiles = [];
let totalRecords = 0;
let authToken = null;
let currentUser = null;
let selectedFiles = [];
let processedResults = [];
let rawExtractions = [];
let structuredRecords = [];

// Global variable to store current header configuration
let currentHeaderConfig = null;

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
    console.log('Debug: Token available:', token);
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
    console.log('Debug: initializeApp() called');

    // Set up the file upload functionality
    setupFileUpload();

    // Set up the export options
    setupExportOptions();

    // Load header configurations with a small delay to ensure token is ready
    console.log('Debug: About to call loadHeaderConfigurations() from initializeApp');
    setTimeout(() => {
        console.log('Debug: Delayed call to loadHeaderConfigurations()');
        loadHeaderConfigurations();
    }, 100);

    // Enable clear button
    const clearBtn = document.getElementById('clear-button');
    if (clearBtn) clearBtn.disabled = false;

    // Add Refresh Results handler
    const refreshBtn = document.getElementById('refreshBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', async () => {
            const original = refreshBtn.innerHTML;
            try {
                refreshBtn.disabled = true;
                refreshBtn.innerHTML = '<i class="fas fa-sync fa-spin"></i> Refreshing...';
                await updateSessionStatus();
                updateExtractionResults();
                showStatusMessage('Results refreshed', 'success');
            } catch (e) {
                console.error('Failed to refresh results:', e);
                showStatusMessage('Failed to refresh results', 'error');
            } finally {
                refreshBtn.disabled = false;
                refreshBtn.innerHTML = original;
            }
        });
    }

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
async function loadHeaderConfigurations(retryCount = 0) {
    const maxRetries = 3;

    try {
        console.log(`Debug: Starting to load header configurations... (attempt ${retryCount + 1})`);

        const token = getToken();
        console.log('Debug: Token available:', !!token);

        if (!token) {
            if (retryCount < maxRetries) {
                console.log(`Debug: No token available, retrying in ${(retryCount + 1) * 500}ms...`);
                setTimeout(() => loadHeaderConfigurations(retryCount + 1), (retryCount + 1) * 500);
                return;
            } else {
                console.error('No authentication token available for header configurations after retries');
                return;
            }
        }

        const url = '/api/header-config/';
        console.log('Debug: Making request to:', url);

        const response = await fetch(url, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        console.log('Debug: Response status:', response.status, response.statusText);

        if (response.ok) {
            const configs = await response.json();
            console.log('Debug: Loaded header configurations:', configs);
            console.log('Debug: Number of configurations:', configs.length);

            // Get both dropdowns
            const exportDropdown = document.getElementById('header-config-dropdown');
            const uploadDropdown = document.getElementById('upload-header-config');

            console.log('Debug: Export dropdown found:', !!exportDropdown);
            console.log('Debug: Upload dropdown found:', !!uploadDropdown);

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
                console.log('Debug: Processing config:', config.name, 'ID:', config.id, 'Default:', config.is_default);

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

            console.log('Debug: Upload dropdown final state:',
                uploadDropdown ? Array.from(uploadDropdown.options).map(opt => ({ value: opt.value, text: opt.textContent })) : 'dropdown not found');

            console.log('Debug: Header configurations loaded successfully');
        } else {
            console.error('Failed to load header configurations. Status:', response.status);
            const errorText = await response.text();
            console.error('Error response:', errorText);
        }
    } catch (error) {
        console.error('Error loading header configurations:', error);
        console.error('Error stack:', error.stack);
    }
}

// Test function for manual debugging
window.testHeaderConfigs = async function () {
    console.log('=== MANUAL HEADER CONFIG TEST ===');
    console.log('Token available:', !!getToken());
    console.log('Upload dropdown exists:', !!document.getElementById('upload-header-config'));
    console.log('Export dropdown exists:', !!document.getElementById('header-config-dropdown'));

    try {
        await loadHeaderConfigurations();
        console.log('=== TEST COMPLETED ===');
    } catch (error) {
        console.error('=== TEST FAILED ===', error);
    }
};

// Test function for process button
window.testProcessButton = function () {
    console.log('=== PROCESS BUTTON TEST ===');
    const button = document.getElementById('processBtn');
    console.log('Process button exists:', !!button);
    console.log('Process button disabled:', button ? button.disabled : 'N/A');
    console.log('Process button innerHTML:', button ? button.innerHTML : 'N/A');
    console.log('Selected files count:', selectedFiles.length);
    console.log('Selected files:', selectedFiles);

    if (button) {
        console.log('Simulating button click...');
        button.click();
    }
    console.log('=== TEST COMPLETED ===');
};

function setupFileUpload() {
    console.log('Debug: setupFileUpload() called');

    // Get DOM elements
    const fileInput = document.getElementById('fileInput');
    const dropArea = document.getElementById('uploadArea');
    const fileList = document.getElementById('fileList');
    const uploadButton = document.getElementById('processBtn');
    const clearButton = document.getElementById('clear-button');

    console.log('Debug: DOM elements found:', {
        fileInput: !!fileInput,
        dropArea: !!dropArea,
        fileList: !!fileList,
        uploadButton: !!uploadButton,
        clearButton: !!clearButton
    });

    if (!dropArea || !fileInput || !fileList || !uploadButton || !clearButton) {
        console.error("Required file upload elements not found");
        console.error("Missing elements:", {
            dropArea: !dropArea,
            fileInput: !fileInput,
            fileList: !fileList,
            uploadButton: !uploadButton,
            clearButton: !clearButton
        });
        return;
    }

    console.log('Debug: All DOM elements found, setting up event listeners...');

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
        console.log('Debug: Process button clicked!');
        console.log('Debug: Selected files count:', selectedFiles.length);
        console.log('Debug: Selected files:', selectedFiles);

        e.preventDefault();
        if (selectedFiles.length > 0) {
            console.log('Debug: Starting file upload process...');
            // Disable button and show loading state
            this.disabled = true;
            this.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';

            uploadFiles(selectedFiles);
        } else {
            console.log('Debug: No files selected, button click ignored');
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

    async function handleFiles(files) {
        if (files.length === 0) return;

        // File limits configuration
        const FILE_LIMITS = {
            MAX_REGULAR_FILES: 10,
            SUPPORTED_TYPES: ['.pdf', '.png', '.jpg', '.jpeg', '.webp', '.zip']
        };

        showStatusMessage('Processing files...', 'info');

        try {
            // Process all files (extract ZIPs)
            const processedFiles = await processAllFiles(Array.from(files));

            // Validate final count
            if (selectedFiles.length + processedFiles.length > FILE_LIMITS.MAX_REGULAR_FILES) {
                throw new Error(`Total files would exceed limit: ${selectedFiles.length + processedFiles.length}/${FILE_LIMITS.MAX_REGULAR_FILES}`);
            }

            // Add processed files to selection
            selectedFiles = [...selectedFiles, ...processedFiles];

            // Update UI
            updateFileList();

            // Show success message
            const fileCount = processedFiles.length;
            const fileWord = fileCount === 1 ? 'file' : 'files';
            showStatusMessage(`${fileCount} ${fileWord} selected and ready to upload`, 'success');

            // Enable upload and clear buttons
            uploadButton.disabled = false;
            clearButton.disabled = false;

        } catch (error) {
            showStatusMessage(`Error processing files: ${error.message}`, 'error');
        }
    }

    async function processAllFiles(files) {
        const processedFiles = [];

        for (const file of files) {
            if (file.name.toLowerCase().endsWith('.zip')) {
                showStatusMessage(`Extracting ZIP file: ${file.name}`, 'info');
                const extractedFiles = await extractZipFile(file);
                processedFiles.push(...extractedFiles);
                showStatusMessage(`Extracted ${extractedFiles.length} files from ${file.name}`, 'success');
            } else {
                // Validate regular file
                if (validateSingleFile(file)) {
                    processedFiles.push(file);
                }
            }
        }

        return processedFiles;
    }

    async function extractZipFile(zipFile) {
        try {
            // Dynamically import JSZip (you'll need to include this library)
            // For now, we'll use a fallback approach with manual ZIP handling

            if (typeof JSZip === 'undefined') {
                throw new Error('JSZip library not loaded. Please include JSZip to handle ZIP files.');
            }

            const zip = new JSZip();
            const contents = await zip.loadAsync(zipFile);

            const extractedFiles = [];
            const promises = [];

            contents.forEach((relativePath, zipEntry) => {
                // Skip directories
                if (zipEntry.dir) return;

                // Filter out system files and metadata
                if (isSystemFile(relativePath)) return;

                const ext = '.' + relativePath.split('.').pop().toLowerCase();

                if (['.pdf', '.png', '.jpg', '.jpeg', '.webp'].includes(ext)) {
                    // Extract file content as blob
                    const promise = zipEntry.async('blob').then(blob => {
                        // Clean up the filename (remove directory paths for display)
                        const cleanFileName = relativePath.split('/').pop() || relativePath;

                        // Create a File object from the blob
                        const file = new File([blob], cleanFileName, {
                            type: getContentType(ext)
                        });
                        // Mark as extracted for UI display
                        file.extractedFrom = zipFile.name;
                        extractedFiles.push(file);
                    });
                    promises.push(promise);
                }
            });

            await Promise.all(promises);

            if (extractedFiles.length === 0) {
                throw new Error('ZIP file contains no supported files (PDF, PNG, JPG, JPEG, WebP)');
            }

            return extractedFiles;

        } catch (error) {
            console.error('Error extracting ZIP file:', error);
            throw new Error(`Failed to extract ZIP file: ${error.message}`);
        }
    }

    function validateSingleFile(file) {
        const FILE_LIMITS = {
            SUPPORTED_TYPES: ['.pdf', '.png', '.jpg', '.jpeg', '.webp']
        };

        const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
        const allowedTypes = [
            'application/pdf',
            'image/png',
            'image/jpeg',
            'image/webp'
        ];

        if (!allowedTypes.includes(file.type) && !FILE_LIMITS.SUPPORTED_TYPES.includes(fileExtension)) {
            showStatusMessage(`Unsupported file type: ${file.name}. Only PDF, PNG, JPG, JPEG, WebP files are supported.`, 'error');
            return false;
        }

        return true;
    }

    function getContentType(extension) {
        const mimeTypes = {
            '.pdf': 'application/pdf',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.webp': 'image/webp'
        };
        return mimeTypes[extension] || 'application/octet-stream';
    }

    function isSystemFile(relativePath) {
        // Filter out system files and metadata from various operating systems
        const systemPatterns = [
            // macOS system files
            '__MACOSX',
            '.DS_Store',
            '._.DS_Store',
            '._',
            '.fseventsd',
            '.Spotlight-V100',
            '.TemporaryItems',
            '.Trashes',
            '.VolumeIcon.icns',
            '.com.apple.',

            // Windows system files
            'Thumbs.db',
            'ehthumbs.db',
            'Desktop.ini',
            '$RECYCLE.BIN',
            'System Volume Information',

            // Linux system files
            '.directory',
            '.trash',

            // General hidden files and directories
            '.git',
            '.svn',
            '.hg',
            'node_modules',
            '.env'
        ];

        // Convert to lowercase for case-insensitive matching
        const pathLower = relativePath.toLowerCase();

        // Check if the path contains any system patterns
        for (const pattern of systemPatterns) {
            if (pathLower.includes(pattern.toLowerCase())) {
                return true;
            }
        }

        // Check if it's a hidden file (starts with .)
        const fileName = relativePath.split('/').pop() || '';
        if (fileName.startsWith('.')) {
            return true;
        }

        // Check if it's in a hidden directory
        if (relativePath.includes('/.')) {
            return true;
        }

        return false;
    }

    function updateFileList() {
        fileList.innerHTML = '';

        // Show file counter
        const fileCounter = document.createElement('div');
        fileCounter.className = 'file-counter';
        fileCounter.textContent = `${selectedFiles.length}/10 files selected`;
        fileList.appendChild(fileCounter);

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

            // Display name with ZIP indication
            const displayName = file.extractedFrom ?
                `${file.name} <small>(from ${file.extractedFrom})</small>` :
                file.name;

            fileItem.innerHTML = `
                <div class="file-name">
                    <i class="fas ${fileIcon}"></i>
                    ${displayName} (${formatFileSize(file.size)})
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
    console.log('Debug: uploadFiles() called with files:', files);
    console.log('Debug: Number of files:', files.length);

    showProgressBar(true);
    showStatusMessage('Starting upload process...', 'info');

    // Get reference to upload button
    const uploadButton = document.getElementById('processBtn');

    try {
        // Step 1: Request presigned URLs
        showStatusMessage('Requesting upload URLs...', 'info');
        const fileMetadata = files.map(file => ({
            filename: file.name,
            content_type: file.type || getContentType('.' + file.name.split('.').pop().toLowerCase()),
            size: file.size
        }));

        const presignedResponse = await requestPresignedUrls(fileMetadata);

        // Step 2: Upload files to S3
        showStatusMessage('Uploading files to S3...', 'info');
        const uploadResults = await uploadFilesToS3(files, presignedResponse.presigned_urls);

        // Step 3: Call extract-new endpoint with file references
        showStatusMessage('Processing files with AI...', 'info');
        const extractResults = await callExtractNewEndpoint(uploadResults);

        // Step 4: Display results
        displayResults(extractResults);

        // Clear selected files after successful processing
        clearSelectedFiles();

        // Update session status to refresh data
        await updateSessionStatus();

        // Update extraction results display
        updateExtractionResults();

    } catch (error) {
        console.error('Error in upload process:', error);
        showStatusMessage(`Error: ${error.message}`, 'error');
    } finally {
        showProgressBar(false);

        // Reset button state
        if (uploadButton) {
            uploadButton.disabled = true;
            uploadButton.innerHTML = 'Process Files';
        }
    }
}

async function requestPresignedUrls(fileMetadata) {
    const token = getToken();

    const response = await fetch('/api/request-presigned-urls', {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(fileMetadata)
    });

    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `Failed to get upload URLs: ${response.status}`);
    }

    return await response.json();
}

async function uploadFilesToS3(files, presignedUrls) {
    const uploadResults = [];

    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const urlData = presignedUrls[i];

        try {
            // Upload file to S3 using presigned URL
            const uploadResponse = await fetch(urlData.presigned_url, {
                method: 'PUT',
                body: file,
                headers: {
                    'Content-Type': urlData.content_type
                }
            });

            if (!uploadResponse.ok) {
                throw new Error(`Failed to upload ${file.name}: ${uploadResponse.status}`);
            }

            // Create S3 file reference
            uploadResults.push({
                file_id: urlData.file_id,
                file_key: urlData.file_key,
                filename: urlData.filename,
                content_type: urlData.content_type,
                size: file.size
            });

            console.log(`Successfully uploaded: ${file.name}`);

        } catch (error) {
            console.error(`Failed to upload ${file.name}:`, error);
            throw new Error(`Upload failed for ${file.name}: ${error.message}`);
        }
    }

    return uploadResults;
}

async function callExtractNewEndpoint(uploadResults) {
    const token = getToken();

    // Get header configuration if selected
    const headerConfigId = document.getElementById('upload-header-config').value;
    const extractRequest = {
        files: uploadResults,
        header_config_id: headerConfigId && headerConfigId.trim() !== '' ? headerConfigId : null
    };

    const response = await fetch('/api/extract-new', {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(extractRequest)
    });

    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `Extraction failed: ${response.status}`);
    }

    return await response.json();
}

function displayResults(extractResults) {
    // Check for errors
    if (extractResults.errors && extractResults.errors.length > 0) {
        const errorMessages = extractResults.errors.map(err =>
            `<li><strong>${err.filename}</strong>: ${err.error}</li>`
        ).join('');

        if (extractResults.results && extractResults.results.length > 0) {
            showStatusMessage(`Processed ${extractResults.results.length} records with some errors: <ul>${errorMessages}</ul>`, 'warning');
        } else {
            showStatusMessage(`Failed to process files: <ul>${errorMessages}</ul>`, 'error');
        }
    } else {
        showStatusMessage(`Successfully processed ${extractResults.results ? extractResults.results.length : 0} records.`, 'success');
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
    const resultsPlaceholder = document.getElementById('resultsPlaceholder');
    const resultsTableContainer = document.getElementById('resultsTableContainer');
    const resultsTableHead = document.getElementById('resultsTableHead');
    const resultsTableBody = document.getElementById('resultsTableBody');
    const exportSection = document.getElementById('exportSection');

    const records = structuredRecords.length > 0 ? structuredRecords : rawExtractions;

    if (!records || records.length === 0) {
        if (resultsPlaceholder) resultsPlaceholder.style.display = 'flex';
        if (resultsTableContainer) resultsTableContainer.style.display = 'none';
        if (exportSection) exportSection.style.display = 'none';
        return;
    }

    // Get field names to use (custom headers if available, otherwise generate from field name)
    function getFieldDisplayName(field) {
        if (currentHeaderConfig && currentHeaderConfig.header_mappings && currentHeaderConfig.header_mappings[field]) {
            return currentHeaderConfig.header_mappings[field];
        }
        // Convert field name to readable format (snake_case to Title Case)
        return field.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }

    // Analyze data to find which fields have values
    const fieldsWithData = new Set();
    records.forEach(record => {
        Object.keys(record).forEach(key => {
            const value = record[key];
            // Less strict filtering - only exclude truly empty values
            if (value !== null && value !== undefined && value !== '') {
                fieldsWithData.add(key);
            }
        });
    });

    // Convert to array and sort alphabetically for consistent display
    const sortedFields = Array.from(fieldsWithData).sort();

    // Clear previous results
    if (resultsTableHead) resultsTableHead.innerHTML = '';
    if (resultsTableBody) resultsTableBody.innerHTML = '';

    // Create dynamic table headers and rows
    if (sortedFields.length > 0 && resultsTableHead && resultsTableBody) {
        const headerRow = document.createElement('tr');
        sortedFields.forEach(field => {
            const th = document.createElement('th');
            th.textContent = getFieldDisplayName(field);
            th.setAttribute('data-field', field); // Store field name for reference
            headerRow.appendChild(th);
        });
        resultsTableHead.appendChild(headerRow);

        // Add rows for each record
        records.forEach(record => {
            const row = document.createElement('tr');
            sortedFields.forEach(field => {
                const td = document.createElement('td');
                const value = record[field];

                // Format the value appropriately
                if (value === null || value === undefined || value === '') {
                    td.textContent = '-';
                    td.className = 'empty-value';
                } else if (field === 'other_details' && typeof value === 'object') {
                    // Handle JSON objects in other_details
                    td.textContent = JSON.stringify(value, null, 2);
                    td.className = 'json-data';
                } else {
                    // Display the actual value
                    td.textContent = String(value);
                }

                row.appendChild(td);
            });
            resultsTableBody.appendChild(row);
        });
    }

    if (resultsPlaceholder) resultsPlaceholder.style.display = 'none';
    if (resultsTableContainer) resultsTableContainer.style.display = 'block';
    if (exportSection) exportSection.style.display = 'block';

    // Load header configurations for the export dropdown
    loadHeaderConfigurations();
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
        url = '/api/download-json';
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