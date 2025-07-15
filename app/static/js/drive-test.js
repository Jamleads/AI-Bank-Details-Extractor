/**
 * Test script for Google Drive integration
 */

// Check if Google Drive API is available
function checkDriveAvailability() {
    fetch('/drive/auth', { method: 'HEAD' })
        .then(response => {
            if (response.ok) {
                console.log('Google Drive API is available');
            } else {
                console.error('Google Drive API is not available');
            }
        })
        .catch(error => {
            console.error('Error checking Google Drive API:', error);
        });
}

// Test function to export to Google Drive
async function testDriveExport() {
    try {
        const response = await fetch('/drive/export', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                file_name: 'test_export.csv',
                format: 'csv',
                use_raw: true
            })
        });

        const result = await response.json();
        console.log('Drive export result:', result);
        return result;
    } catch (error) {
        console.error('Error testing Drive export:', error);
        return null;
    }
}

// Initialize tests
document.addEventListener('DOMContentLoaded', function () {
    console.log('Drive test script loaded');
    checkDriveAvailability();
}); 