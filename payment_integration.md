Integrating Yativo for One-Time International Payments in FastAPI
Yativo Overview: Yativo is a payments infrastructure platform that enables businesses to collect and send money globally via local banking rails and stablecoins
yativo.com
. Unlike traditional gateways that rely on credit card networks, Yativo emphasizes local payment methods (bank transfers, direct debits, etc.) to avoid common card payment issues (declines, fraud, chargebacks, high fees)
yativo.com
. This makes it well-suited for accepting one-time payments from international customers, as funds are collected through local rails with instant settlement and high success rates. In this guide, we’ll walk through setting up Yativo with a Python FastAPI backend to accept one-time payments for your SaaS product, covering the full payment flow, API calls, webhook handling, and data storage considerations.
Setup: Yativo Account and API Key Configuration
Create and Verify a Yativo Business Account: Start by signing up for a Yativo business account (use the Sandbox for testing). You’ll need to complete KYB (Know Your Business) verification and any required documentation. Once approved, you can access the Yativo Dashboard
docs.yativo.com
.
Obtain API Keys: In your Yativo dashboard, generate your API credentials (public and secret API keys) for authentication
docs.yativo.com
. Keep these keys secure – you’ll use the secret key on your backend to authorize API calls. Yativo provides separate endpoints for sandbox (testing) and production:
Production Base URL: https://api.yativo.com
docs.yativo.com
 (use after your account is fully verified).
Sandbox Base URL: https://sandbox.yativo.com (listed as smtp.yativo.com in docs)
docs.yativo.com
, for testing payment flows without real transactions.
Security & Environment: All API requests must include the secret key in a Bearer token (e.g. Authorization: Bearer <YOUR_SECRET_KEY>). Use HTTPS and handle keys securely (e.g., via environment variables in FastAPI). For development, point to the sandbox environment; switch to the production URL and keys when going live
docs.yativo.com
docs.yativo.com
.
Frontend Integration Options with Yativo
Yativo offers flexible options to handle the payment experience on the frontend:
Hosted Checkout Page (Payment Links): You can generate a Yativo checkout URL via their API and redirect users to this hosted page for payment. Yativo Checkouts allow you to collect funds via local payment methods through a simple link
youtube.com
. This hosted page will present the user with the necessary payment instructions (e.g. local bank account details, reference codes, or other steps depending on country).
Embedded Payment Widget: For a more seamless UX, Yativo supports embedding their payment interface as a widget on your site
youtube.com
. This could be an iframe or SDK-driven component that displays the local payment instructions or bank transfer flow within your application’s UI. Using the embed option, customers can follow on-screen prompts (for example, viewing a bank account number/QR code for transfer or authorizing a direct debit) without leaving your site.
SDKs and Libraries: Yativo indicates that they have SDKs/plugins to ease integration
yativo.com
. Check Yativo’s documentation or GitHub for client libraries. If an official JavaScript SDK is available, you could use it to open the checkout or embed the widget. Otherwise, implementing the redirect or iframe manually (using the URL from the API) is straightforward.
Note: Yativo primarily supports non-card payment methods (local bank transfers, stablecoin on-ramps, etc.) for international collections
yativo.com
. This means users will generally pay via bank transfer or similar, rather than entering credit card details on your site. One-time “card payments” in the traditional sense are not the focus – instead, Yativo’s one-time pay-ins are handled through these alternative rails to improve success rates and eliminate chargebacks
yativo.com
. Ensure your UI clearly communicates the payment method (e.g. “Pay via local bank transfer”) when using Yativo.
Payment Flow Overview
Integrating Yativo for a one-time payment involves both backend API calls and front-end user interactions. Below is a step-by-step flow:
Initiate Payment Request (Frontend): When a user chooses to purchase one-time access (e.g. clicking “Buy Now”), your frontend should gather basic info: the amount to charge, currency, and possibly the customer’s country or chosen payment method. You might also require the user to be logged in or provide an identifier so you can link the payment to their account.
Determine Available Payment Methods (Backend): Using the Yativo API, your FastAPI backend will fetch the payment options appropriate for the user:
Get Supported Currencies: Call GET /payment-methods/payin/currency?country={COUNTRY_CODE} to retrieve what currencies can be accepted from the user’s country
docs.yativo.com
. For example, for a user in the UK (GBR), this might return ["GBP","USD","EUR"] if those are allowed.
Get Payment Gateways: Next, call GET /payment-methods/payin?country={COUNTRY_CODE}&currency={CURRENCY} to get a list of available payment methods (gateways) for that country/currency combination
docs.yativo.com
. The response will include gateway identifiers and descriptions – e.g., a specific local bank transfer network or payment partner. Each gateway corresponds to a different channel (for instance, a local bank transfer route, a direct debit option, etc.).
Your backend should choose the appropriate gateway for the scenario. This could be done automatically (if you prefer a specific method) or by sending the list to the frontend for the user to choose a method. For simplicity, you might default to the primary local bank transfer method.
Create a Payin (One-Time Payment) (Backend): Once you have a gateway ID and currency, instruct Yativo to create a new deposit transaction:
Endpoint: POST /wallet/deposits/new
Payload: JSON with "gateway": <ID>, "amount": <amount>, "currency": "<CUR>", and optionally "customer_id": "<UUID>"
docs.yativo.com
.
Customer ID: It’s recommended to create a Yativo Customer for each of your users and include customer_id in the deposit request, so the payment is attributed to that user
docs.yativo.com
. (You can create a customer via POST /customers in the API beforehand and store the returned ID.) If no customer_id is provided, the deposit will top-up your business’s main account balance
docs.yativo.com
.
Response: The response will include a unique identifier for the deposit (e.g., deposit_id or transaction_id) and likely instructions or a URL for completing the payment
docs.yativo.com
. For instance, Yativo may return a payment checkout URL or bank transfer details. Save the deposit_id and any relevant info from this response in your database (for reconciliation and linking with webhooks).
Example: If gateway 235 corresponds to “Local Bank Transfer” in the chosen country, and you want to charge $109, you would send { "gateway": 235, "amount": 109, "currency": "USD", "customer_id": "<user-uuid>" } in the POST request
docs.yativo.com
. Yativo would respond with a JSON containing a status (e.g. success), the deposit’s ID, and possibly a payment link or reference.
Present Payment Instructions to User (Frontend): With the deposit created, now guide the user to actually pay:
Hosted Page Redirect: If Yativo provided a checkout URL in the response, redirect the user to that URL (e.g., open in a new tab or within an iframe). The hosted page will show the user exactly how to complete the payment. For a bank transfer method, the page might display the local bank account details (account number, bank name, reference code, etc.) where the user needs to send the money.
Embedded Widget: If using the widget approach, initialize it with the details from the deposit response. For example, you might include a script that loads the Yativo widget and call a method to render the payment instructions for the specific deposit_id. This way, the user sees the instructions directly on your site.
At this stage, the user will follow the given instructions to pay. In practice, this might mean the user opens their banking app to make a transfer, confirms a direct debit, or performs some local payment step. There is no card number entry here – the user is paying through their local bank or other non-card method.
Payment Completion & Webhook Notification (Backend): Yativo processes the incoming payment via the selected gateway. Once the user’s payment is received/confirmed by Yativo’s system, Yativo will notify your backend via a webhook callback. You must set up a webhook endpoint to handle payment status updates:
Register Webhook URL: Call POST /business/webhook with your endpoint URL to tell Yativo where to send notifications
docs.yativo.com
. (Alternatively, configure it in the Yativo dashboard if available.) The response will confirm your webhook registration. Yativo can send events for various activities; by default these may be categorized as “general” events which include payment updates.
Listen for Payment Events: When the user’s deposit is completed (or if it fails/expires), Yativo will send an HTTP POST to your webhook URL containing the event data. For example, a successful payment might trigger an event like deposit.completed with details such as the deposit ID, status = “success”, amount, currency, and timestamp. Important: You should verify the webhook’s authenticity (Yativo may provide a signature or secret for verification – check the secret field in webhook registration and use it to validate the payload if provided).
Update Transaction Status: On receiving a webhook, find the corresponding record in your database (e.g., by deposit/transaction ID) and update its status (e.g., mark as Completed/Paid). This is the point at which you confirm the user’s payment. Yativo’s webhook system automates status updates for completed transactions
docs.yativo.com
, so you don’t need to continuously poll the API for payment confirmation.
Grant Access to Your SaaS: Once your backend registers a successful payment (either via webhook or, less ideally, via a manual polling of the transaction status endpoint), you can unlock the one-time access for the user. This might involve updating the user’s account in your database (e.g., setting a flag like access_granted=true or provisioning whatever resource was purchased). After updating, you can respond to the webhook (HTTP 200 OK) to acknowledge it. You may also notify the user on the frontend (e.g., show a “Payment Successful” message or send a confirmation email/receipt).
Tip: In cases where the payment method isn’t instant (e.g., user must perform a manual transfer), the webhook might arrive with a delay (minutes or hours later). It’s wise to inform the user if there’s any delay (“We will activate your access as soon as your payment is received.”). Yativo boasts fast settlements (often minutes) for local transfers
yativo.com
, but this can vary by method.
FastAPI Implementation (Code Snippets)
Below are simplified examples of how you might implement the integration in Python with FastAPI: 1. Yativo API Client (Backend) – Using requests to call Yativo endpoints. This could be abstracted into a service class/module.
import requests

YATIVO_SECRET_KEY = "<YOUR_YATIVO_SECRET>"  # Securely load this from env or config
BASE_URL = "https://api.yativo.com/api/v1"   # or sandbox base for testing

headers = {"Authorization": f"Bearer {YATIVO_SECRET_KEY}", "Content-Type": "application/json"}

def get_payin_currencies(country_code: str):
    url = f"{BASE_URL}/payment-methods/payin/currency?country={country_code}"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json().get("data", [])  # assuming 'data' holds the list

def get_payin_gateways(country_code: str, currency: str):
    url = f"{BASE_URL}/payment-methods/payin?country={country_code}&currency={currency}"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json().get("data", [])

def create_deposit(amount: float, currency: str, gateway_id: int, customer_id: str = None):
    payload = {"gateway": gateway_id, "amount": amount, "currency": currency}
    if customer_id:
        payload["customer_id"] = customer_id
    url = f"{BASE_URL}/wallet/deposits/new"
    resp = requests.post(url, json=payload, headers=headers)
    resp.raise_for_status()
    return resp.json().get("data", {})  # assuming response has 'data' with deposit details
This client provides helper functions to fetch payment methods and create a deposit. In a real implementation, you should handle errors and log responses for debugging. The create_deposit function returns details of the new deposit, which likely include a unique ID and possibly a checkout URL or reference. 2. FastAPI Endpoints (Backend) – Define routes to initiate payment and handle webhooks:
from fastapi import FastAPI, HTTPException, Request

app = FastAPI()

@app.post("/pay") 
def initiate_payment(user_id: str, country: str = "USA"):
    # 1. Determine currency and gateway for the user's country
    currencies = get_payin_currencies(country)
    if not currencies:
        raise HTTPException(400, "No payment methods for this country")
    currency = currencies[0]  # choose a currency (e.g., first supported or based on product pricing)
    gateways = get_payin_gateways(country, currency)
    if not gateways:
        raise HTTPException(400, "No payment gateways available for chosen currency")
    gateway_id = gateways[0]["id"]  # pick the appropriate gateway ID (could also filter by type)
    
    # 2. (Optional) Get or create Yativo customer for this user
    customer_id = get_or_create_yativo_customer(user_id)  # assume you implement this if using customers
    
    # 3. Create the deposit (one-time payment)
    deposit_data = create_deposit(amount=... , currency=currency, gateway_id=gateway_id, customer_id=customer_id)
    deposit_id = deposit_data.get("id")
    checkout_url = deposit_data.get("checkout_url") or deposit_data.get("link")
    
    # 4. Store transaction in DB with status "pending"
    save_transaction(user_id, deposit_id, amount, currency, status="pending", gateway=gateway_id)
    
    # 5. Return info to frontend
    return {"checkout_url": checkout_url, "deposit_id": deposit_id}
In this /pay endpoint, you would replace amount=... with the actual amount (perhaps determined by your product’s price or passed in the request). We fetch supported currency and gateway, create a deposit, save the transaction to our database, and return a checkout_url (if provided by Yativo) along with the deposit_id. The frontend can use the URL to redirect the user. If Yativo instead returns bank instructions rather than a URL, you could return those details and display them in the UI. Next, set up a webhook endpoint to receive Yativo’s notifications:
@app.post("/webhook")
async def yativo_webhook(request: Request):
    payload = await request.json()
    # (Optional) Verify authenticity using a stored webhook secret or signature if provided by Yativo
    
    event_type = payload.get("event") or payload.get("events") or payload.get("type")
    data = payload.get("data", {})
    
    # Check if this is a deposit (payin) completion event
    # (Yativo might not specify a separate event name; you may need to infer from data)
    deposit_id = data.get("id") or data.get("deposit_id")
    status = data.get("status")
    
    if deposit_id and status:
        # Update transaction in DB
        update_transaction_status(deposit_id, status=status)
        if status.lower() in ("completed", "success"):
            # Grant user access since payment succeeded
            user = get_user_by_transaction(deposit_id)
            if user:
                grant_one_time_access(user)
        # You could handle "failed" or "expired" statuses similarly (e.g., notify user to retry)
    
    return {"received": True}
Here we parse the JSON payload sent by Yativo. The exact structure of the webhook JSON will depend on Yativo’s implementation. According to Yativo, the webhook will send status notifications for events
docs.yativo.com
. We look for a deposit ID and status in the payload, then update our records accordingly. Make sure to respond with a 2XX status quickly. FastAPI returning {"received": True} with status 200 tells Yativo that you’ve handled the webhook (preventing retries). Webhook security: Yativo’s webhook creation response includes a secret field
docs.yativo.com
 which might be used to sign webhook payloads. If so, use it to verify the X-Signature header (or similar) in the request. This ensures the request truly comes from Yativo. Always implement verification if available, and prefer using HTTPS with a strong, unguessable URL for the webhook endpoint.
Relevant Yativo API Endpoints Summary
For clarity, here is a summary of the key API calls used in the integration, and their purpose:
API Endpoint	Purpose
GET /payment-methods/payin/currency?country={CODE}	Get supported deposit currencies for a given country (e.g. GBR for UK)
docs.yativo.com
. Use this to decide which currency the user can pay in.
GET /payment-methods/payin?country={CODE}&currency={CUR}	Get available payment gateways (methods) for the specified country and currency
docs.yativo.com
. Each gateway ID corresponds to a payment method (e.g. local bank network, Pix, CLABE, etc.).
POST /wallet/deposits/new	Create a new deposit (pay-in) transaction
docs.yativo.com
. You provide the gateway ID, amount, currency, and optionally a customer ID. Returns a deposit reference (ID) and possibly payment instructions or link.
POST /business/webhook	Register your webhook URL with Yativo
docs.yativo.com
. Yativo will post payment status events to this URL. (Call this once during setup or update as needed.)
GET /transactions/{id} or GET /transaction/{deposit_id}	(Assumed) Retrieve details of a specific transaction. Yativo’s docs suggest endpoints for transaction status inquiry
docs.yativo.com
. Use this if you need to manually check a payment’s status (e.g., if webhook was missed).
(Note: Replace {CODE} with country ISO code (e.g. USA, MEX), {CUR} with currency code, and {id} with the transaction ID as appropriate. The exact endpoint for fetching a deposit’s status might be /transactions or accessible via the “Transaction Summary” API.)
Database Schema and Data Storage
Design your database to securely store user and payment information, linking Yativo transactions to your users. Here’s a suggested schema structure: Users Table: Stores your SaaS users (if not already existing). For payments, include a field to map to Yativo’s customer ID if you use Yativo’s customer object. For example:
user_id (PK) – Unique identifier for your user.
name, email, etc. – User’s info.
yativo_customer_id – Yativo Customer ID associated with this user (if you called POST /customers to create one). This is a UUID provided by Yativo
docs.yativo.com
.
access_granted (boolean or datetime) – Flag or timestamp for the one-time access entitlement. E.g., set to true or set an “access_until” if the access expires.
Payments (Transactions) Table: Stores each payment attempt or transaction:
transaction_id (PK) – Internal ID for the payment record.
user_id (FK to Users) – The user who made the payment.
yativo_deposit_id – Yativo’s Deposit ID for the transaction (to cross-reference with webhooks and queries).
amount and currency – Amount paid and currency code (e.g., 109 and "USD").
payment_method – Text or code for the method (could store Yativo gateway ID or a descriptor like "BankTransfer_US" for reporting).
status – Payment status in your system (e.g., "pending", "completed", "failed"). Initialize as "pending" when created, update to "completed" on successful webhook, or "failed" if informed so.
created_at / updated_at – Timestamps for record creation and last update.
Optional fields: reference or instruction_details – If Yativo provided bank reference numbers or account details for the transfer, you might store them here for auditing. Also, product_id or invoice_id if the payment is tied to a specific purchase entity in your system.
Security Considerations: Do not store sensitive payment details on your servers. With Yativo, you typically won’t handle card numbers at all (since payments are offloaded to bank rails), so this risk is minimized. If any personal data is involved (e.g., user’s bank info for direct debit, or PII from KYC), encrypt it at rest. The Yativo deposit ID and customer ID can be stored as plain identifiers (they are not sensitive by themselves). Ensure your database has proper access controls, and that you only log what’s necessary for troubleshooting (avoid logging full webhook payloads with personal data).
Conclusion
Integrating Yativo into a FastAPI backend for one-time international payments involves a combination of Yativo’s powerful API and careful backend logic to handle the payment lifecycle. You will:
Configure your Yativo account and API keys (using the sandbox for testing).
Use Yativo’s Payin API to create one-time payment transactions for users in their local currency
docs.yativo.com
docs.yativo.com
.
Leverage Yativo’s hosted checkout or widget to present payment instructions to customers, allowing them to pay via local methods (ensuring high success rates even for international clients)
yativo.com
.
Implement webhook handlers to get real-time payment status updates and grant access when a payment is confirmed
docs.yativo.com
.
Store transaction records and user data securely, linking each payment to a user and keeping an audit trail without handling sensitive financial data directly.
By following this flow, your invoice extraction SaaS can accept one-time payments globally through Yativo’s infrastructure. Yativo supports collections in 30+ countries with local settlements
yativo.com
, so as you integrate, consider which regions and currencies you need. Always test the end-to-end flow in the sandbox (simulate a payment, ensure your webhook logic works, and verify that users gain access appropriately). With the above setup, you’ll have a robust, secure payment integration that provides international reach without the headaches of traditional card processing. References:
Yativo Documentation – Payin (Deposit) API
docs.yativo.com
docs.yativo.com
Yativo Documentation – Webhook Setup
docs.yativo.com
Yativo Documentation – Supported Countries & Currencies
yativo.com
Yativo Website – Checkouts (Local Payment Methods vs Card)
yativo.com
Yativo Checkouts Video – Payment Links and Widgets
youtube.com
Yativo Payouts Documentation – API Response contains transaction ID and status
docs.yativo.com
Citations

Yativo Checkouts | Accept Bank Transfers Payments Globally

https://yativo.com/checkouts/

Yativo Checkouts | Accept Bank Transfers Payments Globally

https://yativo.com/checkouts/

Getting Started with Yativo API | Yativo Documentation

https://docs.yativo.com/getting-started-with-yativo-api

Getting Started with Yativo API | Yativo Documentation

https://docs.yativo.com/getting-started-with-yativo-api

Environments | Yativo Documentation

https://docs.yativo.com/environment/environments

Environments | Yativo Documentation

https://docs.yativo.com/environment/environments

Introducing Yativo Checkouts - YouTube

https://www.youtube.com/watch?v=D4o5Ei31njk

Yativo Checkouts | Accept Bank Transfers Payments Globally

https://yativo.com/checkouts/

Payin | Yativo Documentation

https://docs.yativo.com/payments/payin

Payin | Yativo Documentation

https://docs.yativo.com/payments/payin

Payin | Yativo Documentation

https://docs.yativo.com/payments/payin

Payin | Yativo Documentation

https://docs.yativo.com/payments/payin

Payin | Yativo Documentation

https://docs.yativo.com/payments/payin

Payout | Yativo Documentation

https://docs.yativo.com/payments/payout

Webhook | Yativo Documentation

https://docs.yativo.com/notifications/webhook

Yativo Crypto Platform API | Yativo Documentation

https://docs.yativo.com/crypto-system/yativo-crypto-platform-api

Yativo Checkouts | Accept Bank Transfers Payments Globally

https://yativo.com/checkouts/

Webhook | Yativo Documentation

https://docs.yativo.com/notifications/webhook

Payout | Yativo Documentation

https://docs.yativo.com/payments/payout

Payin | Yativo Documentation

https://docs.yativo.com/payments/payin
All Sources

yativo

docs.yativo

youtube