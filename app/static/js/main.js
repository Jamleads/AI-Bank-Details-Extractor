// Global variables
let processedFiles = [];
let totalRecords = 0;
let authToken = null;
let currentUser = null;
let selectedFiles = [];
let processedResults = [];

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

    // Check if user is logged in
    checkAuth().then((isAuthenticated) => {
        if (isAuthenticated) {
            // User is authenticated, load app
            console.log("User is authenticated, loading app");
            loadApp();
        } else {
            // User is not authenticated, show login button
            console.log("User is not authenticated, showing login button");
            showLoginScreen();
        }
    });

    // Setup file upload via button
    const chooseFilesBtn = document.getElementById('chooseFilesBtn');
    const fileInput = document.getElementById('fileInput');
    const uploadSection = document.getElementById('uploadSection');

    if (chooseFilesBtn && fileInput) {
        chooseFilesBtn.addEventListener('click', function () {
            fileInput.click();
        });

        fileInput.addEventListener('change', function (e) {
            handleFileSelection(e.target.files);
        });
    }

    // Setup drag and drop
    if (uploadSection) {
        uploadSection.addEventListener('dragover', function (e) {
            e.preventDefault();
            uploadSection.classList.add('dragover');
        });

        uploadSection.addEventListener('dragleave', function () {
            uploadSection.classList.remove('dragover');
        });

        uploadSection.addEventListener('drop', function (e) {
            e.preventDefault();
            uploadSection.classList.remove('dragover');
            handleFileSelection(e.dataTransfer.files);
        });
    }

    // Check for existing session data
    checkSessionStatus();
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

function showLoginScreen() {
    // Hide app content
    document.getElementById('appContent').style.display = 'none';

    // Show login screen
    const loginScreen = document.createElement('div');
    loginScreen.id = 'loginScreen';
    loginScreen.className = 'login-screen';
    loginScreen.innerHTML = `
        <div class="login-container">
            <h2>Welcome to Bank Details Extractor</h2>
            <p>Please sign in to continue</p>
            <button id="googleLoginBtn" class="google-login-btn">
                <i class="fas fa-google"></i> Sign in with Google
            </button>
        </div>
    `;

    document.querySelector('.main-content').appendChild(loginScreen);

    // Add event listener to login button
    document.getElementById('googleLoginBtn').addEventListener('click', () => {
        window.location.href = '/auth/login';
    });
}

function loadApp() {
    // Show app content
    document.getElementById('appContent').style.display = 'block';

    // Add user info to header
    if (currentUser) {
        const userInfo = document.createElement('div');
        userInfo.className = 'user-info';
        userInfo.innerHTML = `
            <span class="user-name">${currentUser.name || currentUser.email}</span>
            <button id="logoutBtn" class="logout-btn">
                <i class="fas fa-sign-out-alt"></i> Logout
            </button>
        `;

        document.querySelector('.header').appendChild(userInfo);

        // Add event listener to logout button
        document.getElementById('logoutBtn').addEventListener('click', logout);
    }

    // First update session status to get pre-populated files
    updateSessionStatus().then(() => {
        console.log("Session status updated with pre-populated files");
        setupEventListeners();
        console.log("Event listeners set up");
    });
}

function logout() {
    // Clear token and reload page
    clearToken();
    window.location.reload();
}

function setupEventListeners() {
    const uploadSection = document.getElementById('uploadSection');
    const fileInput = document.getElementById('fileInput');
    const chooseFilesBtn = document.getElementById('chooseFilesBtn');

    console.log("Setting up event listeners for upload section");

    // Drag and drop functionality
    uploadSection.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadSection.classList.add('dragover');
    });

    uploadSection.addEventListener('dragleave', () => {
        uploadSection.classList.remove('dragover');
    });

    uploadSection.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadSection.classList.remove('dragover');
        const files = e.dataTransfer.files;
        handleFiles(files);
    });

    // File input change
    fileInput.addEventListener('change', (e) => {
        handleFiles(e.target.files);
    });

    // Choose files button click - separate from the upload section click
    chooseFilesBtn.addEventListener('click', (e) => {
        e.stopPropagation(); // Prevent event from bubbling up to the upload section
        fileInput.click();
    });
}

async function handleFiles(files) {
    console.log("handleFiles called with", files.length, "files");

    if (!files || files.length === 0) {
        console.log("No files selected");
        return;
    }

    // Filter for PDF files
    const pdfFiles = Array.from(files).filter(file => {
        console.log("File:", file.name, "Type:", file.type);
        // Check both MIME type and extension for PDF
        return file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
    });

    console.log("Filtered PDF files:", pdfFiles.length);

    if (pdfFiles.length === 0) {
        showResults('No PDF files selected. Please select PDF files only.', false);
        return;
    }

    for (let file of pdfFiles) {
        console.log("Processing PDF file:", file.name);
        await processFile(file);
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

        // Update UI with file information
        if (status.files && status.files.length > 0) {
            const filesDisplay = document.getElementById('filesDisplay');
            if (filesDisplay) {
                filesDisplay.innerHTML = status.files.map(file =>
                    `<div>${file.name}</div>`
                ).join('');
                filesDisplay.classList.add('has-files');
            }

            const totalFiles = document.getElementById('totalFiles');
            if (totalFiles) {
                totalFiles.textContent = status.files.length;
            }
        }

        // Update total records count
        const totalRecordsElement = document.getElementById('totalRecords');
        if (totalRecordsElement) {
            totalRecordsElement.textContent = status.total_records || 0;
        }

        // Enable download button if we have records
        if (status.total_records > 0) {
            document.getElementById('downloadBtn').disabled = false;
        } else {
            document.getElementById('downloadBtn').disabled = true;
        }

        return status;
    } catch (error) {
        console.error('Error updating session status:', error);
        return null;
    }
}

function updateFilesList(filesDisplay) {
    const filesElement = document.getElementById('filesDisplay');
    filesElement.textContent = filesDisplay;

    if (filesDisplay !== 'No files selected') {
        filesElement.classList.add('has-files');
    } else {
        filesElement.classList.remove('has-files');
    }
}

function updateCounts(records, files) {
    document.getElementById('totalRecords').textContent = records;
    document.getElementById('totalFiles').textContent = files;
}

async function processFile(file) {
    console.log("Processing file:", file.name);
    showLoading(true);
    hideResults();

    try {
        // Create FormData and append the file
        const formData = new FormData();
        formData.append('files', file);
        console.log("Sending request to /api/extract endpoint with file:", file.name);

        // Get token
        const token = getToken();

        // Send the request
        const response = await fetch('/api/extract', {
            method: 'POST',
            body: formData,
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        console.log("Response received:", response.status);

        // Check if response is ok
        if (!response.ok) {
            throw new Error(`Server responded with status: ${response.status}`);
        }

        // Parse the response
        const result = await response.json();
        console.log("Response data:", result);

        if (result.success) {
            // Update UI with results
            showResults(
                `✅ Successfully processed "${file.name}"<br>
                📄 ${result.records_added} new records added<br>
                💾 Data has been added to database`,
                true
            );

            // Update session status to refresh counts and files
            await updateSessionStatus();
        } else {
            console.error("Error in response:", result.error);
            showResults(`❌ Error processing "${file.name}": ${result.error}`, false);
        }
    } catch (error) {
        console.error("Upload failed:", error);
        showResults(`❌ Upload failed: ${error.message}`, false);
    } finally {
        showLoading(false);
    }
}

function showLoading(show) {
    const loadingSection = document.getElementById('loadingSection');
    if (show) {
        loadingSection.classList.add('show');
    } else {
        loadingSection.classList.remove('show');
    }
}

function showResults(message, isSuccess) {
    const resultsSection = document.getElementById('resultsSection');
    const resultsTitle = document.getElementById('resultsTitle');
    const resultsTitleText = document.getElementById('resultsTitleText');
    const resultsContent = document.getElementById('resultsContent');

    // Set content
    resultsContent.innerHTML = message;

    // Set styling based on success/error
    if (isSuccess) {
        resultsSection.classList.remove('error');
        resultsTitle.classList.remove('error');
        resultsTitle.classList.add('success');
        resultsContent.classList.remove('error');
        resultsTitleText.textContent = 'Processing Complete';
    } else {
        resultsSection.classList.add('error');
        resultsTitle.classList.remove('success');
        resultsTitle.classList.add('error');
        resultsContent.classList.add('error');
        resultsTitleText.textContent = 'Processing Error';
    }

    // Show with animation
    resultsSection.classList.add('show', 'fade-in');
}

function hideResults() {
    const resultsSection = document.getElementById('resultsSection');
    resultsSection.classList.remove('show');
}

async function clearSession() {
    if (confirm('Are you sure you want to clear the current session? This will delete all your records.')) {
        try {
            const token = getToken();

            const response = await fetch('/api/clear-session', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (response.ok) {
                // Reset global variables
                processedFiles = [];
                totalRecords = 0;
                selectedFiles = [];
                processedResults = [];

                // Reset UI
                const filesDisplay = document.getElementById('filesDisplay');
                if (filesDisplay) {
                    filesDisplay.innerHTML = 'No files selected';
                    filesDisplay.classList.remove('has-files');
                }

                const totalRecordsElement = document.getElementById('totalRecords');
                if (totalRecordsElement) {
                    totalRecordsElement.textContent = '0';
                }

                const totalFiles = document.getElementById('totalFiles');
                if (totalFiles) {
                    totalFiles.textContent = '0';
                }

                // Disable download button
                const downloadBtn = document.getElementById('downloadBtn');
                if (downloadBtn) {
                    downloadBtn.disabled = true;
                }

                hideResults();
                showResults('✅ Session cleared successfully. All records have been deleted.', true);
            }
        } catch (error) {
            showResults('❌ Error clearing session: ' + error.message, false);
        }
    }
}

// Download CSV of all processed results
function downloadCSV() {
    // Use the correct API endpoint for downloading CSV
    window.location.href = '/api/download-csv';
}

// Handle file selection
function handleFileSelection(files) {
    if (!files || files.length === 0) return;

    // Filter for PDF files only
    const pdfFiles = Array.from(files).filter(file => file.type === 'application/pdf');

    if (pdfFiles.length === 0) {
        showError('Please select PDF files only.');
        return;
    }

    // Add to selected files
    selectedFiles = [...selectedFiles, ...pdfFiles];

    // Update UI
    updateFilesDisplay();

    // Upload files
    uploadFiles(pdfFiles);
}

// Update the files display in the UI
function updateFilesDisplay() {
    const filesDisplay = document.getElementById('filesDisplay');
    const totalFiles = document.getElementById('totalFiles');

    if (filesDisplay) {
        if (selectedFiles.length > 0) {
            filesDisplay.innerHTML = selectedFiles.map(file =>
                `<div>${file.name}</div>`
            ).join('');
            filesDisplay.classList.add('has-files');
        } else {
            filesDisplay.innerHTML = 'No files selected';
            filesDisplay.classList.remove('has-files');
        }
    }

    if (totalFiles) {
        totalFiles.textContent = selectedFiles.length;
    }
}

// Format file size to human-readable format
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';

    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));

    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Upload files to the server
function uploadFiles(files) {
    const loadingSection = document.getElementById('loadingSection');
    const resultsSection = document.getElementById('resultsSection');

    if (loadingSection) {
        loadingSection.classList.add('show');
    }

    if (resultsSection) {
        resultsSection.classList.remove('show');
    }

    const formData = new FormData();
    files.forEach(file => {
        formData.append('files', file);
    });

    fetch('/api/extract', {
        method: 'POST',
        body: formData,
        headers: {
            // Don't set Content-Type with FormData as browser will set it with boundary
        }
    })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            processedResults = [...processedResults, ...data.results];
            updateResults(data);

            if (loadingSection) {
                loadingSection.classList.remove('show');
            }
        })
        .catch(error => {
            console.error('Error uploading files:', error);
            showError('Error processing files. Please try again.');

            if (loadingSection) {
                loadingSection.classList.remove('show');
            }
        });
}

// Update results in the UI
function updateResults(data) {
    const resultsSection = document.getElementById('resultsSection');
    const resultsContent = document.getElementById('resultsContent');
    const resultsTitleText = document.getElementById('resultsTitleText');
    const totalRecords = document.getElementById('totalRecords');

    if (!resultsSection || !resultsContent) return;

    if (data.results && data.results.length > 0) {
        // Show results section
        resultsSection.classList.add('show');
        resultsSection.classList.remove('error');

        // Update title
        if (resultsTitleText) {
            resultsTitleText.textContent = 'Processing Complete';
        }

        // Create results summary
        let resultsHtml = '<div class="results-summary">';
        resultsHtml += `<p>${data.results.length} records extracted successfully.</p>`;

        // Add a preview of the first few records
        const previewCount = Math.min(3, data.results.length);
        resultsHtml += '<div class="results-preview">';
        resultsHtml += '<h3>Preview:</h3>';
        resultsHtml += '<ul>';

        for (let i = 0; i < previewCount; i++) {
            const record = data.results[i];
            resultsHtml += `<li><strong>${record.bank_name || 'Unknown Bank'}</strong>: Account ${record.account_number || 'N/A'}</li>`;
        }

        resultsHtml += '</ul>';

        if (data.results.length > previewCount) {
            resultsHtml += `<p>...and ${data.results.length - previewCount} more records.</p>`;
        }

        resultsHtml += '</div></div>';

        // Update content
        resultsContent.innerHTML = resultsHtml;
        resultsContent.classList.remove('error');

        // Update total records count
        if (totalRecords) {
            totalRecords.textContent = processedResults.length;
        }

        // Enable download button
        const downloadBtn = document.getElementById('downloadBtn');
        if (downloadBtn) {
            downloadBtn.disabled = false;
        }
    } else {
        // Show error
        showError('No bank details found in the uploaded files.');
    }
}

// Show error message
function showError(message) {
    const resultsSection = document.getElementById('resultsSection');
    const resultsContent = document.getElementById('resultsContent');
    const resultsTitleText = document.getElementById('resultsTitleText');

    if (!resultsSection || !resultsContent) return;

    // Show results section with error styling
    resultsSection.classList.add('show');
    resultsSection.classList.add('error');

    // Update title
    if (resultsTitleText) {
        resultsTitleText.textContent = 'Error';
    }

    // Update content
    resultsContent.innerHTML = `<p>${message}</p>`;
    resultsContent.classList.add('error');
}

// Check session status on page load
function checkSessionStatus() {
    fetch('/api/session-status')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.files && data.files.length > 0) {
                // Restore session data
                selectedFiles = data.files.map(fileInfo => {
                    return {
                        name: fileInfo.name,
                        size: fileInfo.size,
                        type: 'application/pdf'
                    };
                });

                processedResults = data.results || [];

                // Update UI
                updateFilesDisplay();

                const totalRecords = document.getElementById('totalRecords');
                if (totalRecords) {
                    totalRecords.textContent = processedResults.length;
                }

                // Show results if available
                if (processedResults.length > 0) {
                    updateResults({
                        results: processedResults
                    });
                }
            }
        })
        .catch(error => {
            console.error('Error checking session status:', error);
        });
} 