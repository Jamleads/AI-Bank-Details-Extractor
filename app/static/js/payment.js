/**
 * Payment handling for AI Bank Details Extractor
 */

// Payment status polling interval (in milliseconds)
const PAYMENT_POLL_INTERVAL = 5000;

// Store active payment polling timers
const activePolls = {};

/**
 * Initialize the payment UI
 */
function initPaymentUI() {
    // Load pricing information
    fetchPricingInfo();

    // Set up event listeners for payment buttons
    document.addEventListener('click', function (event) {
        if (event.target.classList.contains('payment-button')) {
            const tier = event.target.dataset.tier;
            if (tier) {
                initiatePayment(tier);
            }
        }
    });
}

/**
 * Fetch pricing information from the API
 */
async function fetchPricingInfo() {
    try {
        const response = await fetch('/api/payment/pricing');
        if (!response.ok) {
            throw new Error('Failed to fetch pricing information');
        }

        const pricingData = await response.json();
        updatePricingUI(pricingData);
    } catch (error) {
        console.error('Error fetching pricing information:', error);
        showNotification('Error loading pricing information. Please try again later.', 'error');
    }
}

/**
 * Update the pricing UI with data from the API
 */
function updatePricingUI(pricingData) {
    const pricingContainer = document.getElementById('pricing-container');
    if (!pricingContainer) return;

    // Clear existing content
    pricingContainer.innerHTML = '';

    // Create pricing cards
    const tiers = ['free', 'basic', 'pro', 'enterprise'];
    const tierTitles = {
        'free': 'Free',
        'basic': 'Basic',
        'pro': 'Professional',
        'enterprise': 'Enterprise'
    };

    tiers.forEach(tier => {
        if (!pricingData[tier]) return;

        const tierData = pricingData[tier];
        const card = document.createElement('div');
        card.className = 'pricing-card';
        if (tier === 'pro') {
            card.classList.add('featured');
        }

        // Create card content
        let buttonText = tier === 'free' ? 'Start Free' : 'Buy Now';
        let priceDisplay = tier === 'free' ? 'Free' : `$${tierData.price}`;

        card.innerHTML = `
            <div class="pricing-header">
                <h3>${tierTitles[tier]}</h3>
                <div class="pricing-price">${priceDisplay}</div>
                <div class="pricing-period">One-time payment</div>
            </div>
            <div class="pricing-features">
                <ul>
                    ${tierData.features.map(feature => `<li>${feature}</li>`).join('')}
                </ul>
            </div>
            <div class="pricing-action">
                <button class="payment-button" data-tier="${tier.toUpperCase()}">${buttonText}</button>
            </div>
        `;

        pricingContainer.appendChild(card);
    });
}

/**
 * Initiate payment for the selected tier
 */
async function initiatePayment(tier) {
    try {
        // Show loading state
        showLoadingOverlay('Processing your request...');

        console.log(`Initiating payment for tier: ${tier}`);

        // Call API to initiate payment
        const response = await fetch('/api/payment/initiate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                tier: tier.toUpperCase(),  // Convert to uppercase to match backend enum
                country_code: "USA"  // Default to USA
            })
        });

        console.log('Payment API response status:', response.status);

        if (!response.ok) {
            const errorData = await response.json();
            console.error('Payment API error:', errorData);
            throw new Error(errorData.detail || 'Payment initiation failed');
        }

        const paymentData = await response.json();
        console.log('Payment data received:', paymentData);

        // Hide loading overlay
        hideLoadingOverlay();

        // Handle payment based on status
        if (paymentData.status === 'completed') {
            // Free tier or already completed payment
            showPaymentSuccess();

            // Refresh the page to update UI based on new access
            setTimeout(() => {
                window.location.reload();
            }, 2000);
        } else if (paymentData.checkout_url) {
            // Save payment ID in local storage for status checking when user returns
            localStorage.setItem('pendingPaymentId', paymentData.id);

            // Redirect to Yativo's hosted checkout page
            window.location.href = paymentData.checkout_url;
        } else {
            throw new Error('No checkout URL provided');
        }
    } catch (error) {
        hideLoadingOverlay();
        console.error('Payment initiation error:', error);
        showNotification(error.message || 'Failed to initiate payment. Please try again.', 'error');
    }
}

/**
 * Check for pending payments when page loads
 */
function checkPendingPayment() {
    const pendingPaymentId = localStorage.getItem('pendingPaymentId');
    if (pendingPaymentId) {
        // Check the payment status
        checkPaymentStatus(pendingPaymentId, true);
    }
}

/**
 * Check payment status
 */
async function checkPaymentStatus(paymentId, clearPendingAfter = false) {
    try {
        const response = await fetch(`/api/payment/status/${paymentId}`);
        if (!response.ok) {
            throw new Error('Failed to check payment status');
        }

        const paymentData = await response.json();

        // If payment is completed, show success
        if (paymentData.status === 'completed') {
            if (clearPendingAfter) {
                localStorage.removeItem('pendingPaymentId');
            }

            // Show success message
            showPaymentSuccess();

            // Refresh the page to update UI based on new access
            setTimeout(() => {
                window.location.reload();
            }, 2000);
        } else if (paymentData.status === 'failed' || paymentData.status === 'expired') {
            // Payment failed
            if (clearPendingAfter) {
                localStorage.removeItem('pendingPaymentId');
            }

            // Show failure message
            showNotification('Payment failed or expired. Please try again.', 'error');
        }
    } catch (error) {
        console.error('Error checking payment status:', error);
    }
}

/**
 * Show payment success message
 */
function showPaymentSuccess() {
    showNotification('Payment successful! Your account has been upgraded.', 'success');
}

/**
 * Show loading overlay
 */
function showLoadingOverlay(message = 'Loading...') {
    let overlay = document.getElementById('loading-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'loading-overlay';
        overlay.innerHTML = `
            <div class="loading-spinner"></div>
            <div class="loading-message">${message}</div>
        `;
        document.body.appendChild(overlay);
    } else {
        overlay.querySelector('.loading-message').textContent = message;
    }

    overlay.style.display = 'flex';
}

/**
 * Hide loading overlay
 */
function hideLoadingOverlay() {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
        overlay.style.display = 'none';
    }
}

/**
 * Show notification
 */
function showNotification(message, type = 'info') {
    let notification = document.getElementById('notification');
    if (!notification) {
        notification = document.createElement('div');
        notification.id = 'notification';
        document.body.appendChild(notification);
    }

    notification.className = `notification ${type}`;
    notification.textContent = message;
    notification.style.display = 'block';

    // Auto-hide after 5 seconds
    setTimeout(() => {
        notification.style.display = 'none';
    }, 5000);
}

// Initialize payment UI and check for pending payments when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    initPaymentUI();
    checkPendingPayment();
}); 