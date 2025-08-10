#!/usr/bin/env python3
"""
PDF Bank Details Extractor Web Application
Uploads PDF to Google Gemini AI for bank details extraction and generates CSV
"""

import uvicorn
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from app.api.routes import router as api_router
from app.api.auth import router as auth_router
from app.api.header_config import router as header_config_router
from app.api.drive import router as drive_router
from app.api.payment import router as payment_router
from app.api.ads import router as ads_router
from app.core.config import settings
from app.db import init_db
from app.services.auth_service import oauth, get_current_user, get_current_user_required
from app.db.models import User
from app.core.admin_config import is_admin_email

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)

# Reduce AWS SDK logging verbosity (these are very chatty at DEBUG level)
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('s3transfer').setLevel(logging.WARNING)
logging.getLogger('botocore.credentials').setLevel(logging.WARNING)
logging.getLogger('botocore.utils').setLevel(logging.WARNING)
logging.getLogger('botocore.hooks').setLevel(logging.WARNING)
logging.getLogger('botocore.loaders').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Helper function to get user email
def get_user_email(user):
    """Get user email handling both object and dictionary access"""
    if user is None:
        return None
    return user["email"] if isinstance(user, dict) else user.email

# Helper function to normalize user data for templates
def normalize_user_data(user):
    """Convert user object to dictionary for consistent template access"""
    if user is None:
        return None
    
    if isinstance(user, dict):
        # Ensure subscription_tier exists
        if "subscription_tier" not in user:
            user["subscription_tier"] = "FREE"
        elif isinstance(user["subscription_tier"], str) and user["subscription_tier"].lower() in ["free", "basic", "pro", "enterprise"]:
            # Convert to uppercase if it's a lowercase string
            user["subscription_tier"] = user["subscription_tier"].upper()
        return user
    else:
        # Get subscription tier value
        subscription_tier = getattr(user, "subscription_tier", "FREE")
        # If it's an enum, get the value
        if hasattr(subscription_tier, "value"):
            subscription_tier = subscription_tier.value
        # Ensure it's uppercase
        if isinstance(subscription_tier, str) and subscription_tier.lower() in ["free", "basic", "pro", "enterprise"]:
            subscription_tier = subscription_tier.upper()
            
        # Convert SQLAlchemy model to dict
        return {
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "picture": user.picture,
            "google_id": user.google_id,
            "subscription_tier": subscription_tier,
            "subscription_updated_at": getattr(user, "subscription_updated_at", None),
            "created_at": getattr(user, "created_at", None),
            "last_login": getattr(user, "last_login", None)
        }

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI application
    Handles startup and shutdown events
    """
    # Startup: Initialize database
    logger.info("Starting application and initializing database")
    await init_db()
    yield
    # Shutdown: Clean up resources if needed
    logger.info("Shutting down application")
    pass

# Create FastAPI app
app = FastAPI(
    title="Invoice Extractor",
    description="""Extract invoice details from uploaded files

## API Key Authentication

### Getting Your API Key

1. **Log in** to the Invoice Extractor application using your credentials.
2. Navigate to the **API Keys** section by clicking on the "API Keys" link in the main navigation menu.
3. On the API Keys page, click the **Generate New API Key** button to create a new API key.
4. Your new API key will be displayed in the table. Keep this key secure and do not share it with others.
5. You can create multiple API keys and activate/deactivate them as needed.

### Using Your API Key

To authenticate your API requests, include your API key in the `X-API-Key` header with every request:

```bash
curl -X POST "https://your-domain.com/api/extract" \\
  -H "X-API-Key: YOUR_API_KEY" \\
  -F "files=@/path/to/your/invoice.pdf"
```

### Security Best Practices

- Keep your API keys secure and never expose them in client-side code
- Rotate your API keys periodically by generating new ones and deactivating old ones
- Only use API keys in secure, server-to-server communications
- If you suspect an API key has been compromised, deactivate it immediately
""",
    version="1.0.0",
    lifespan=lifespan
)

# Add session middleware - required for OAuth
app.add_middleware(
    SessionMiddleware, 
    secret_key=settings.SECRET_KEY,
    max_age=3600,  # 1 hour session
    same_site="lax",
    https_only=settings.PRODUCTION
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates
templates = Jinja2Templates(directory="app/templates")

# Include API routes
app.include_router(api_router)
app.include_router(auth_router)
app.include_router(header_config_router)
app.include_router(drive_router)
app.include_router(payment_router, prefix="/api/payment", tags=["payment"])
app.include_router(ads_router, prefix="/api", tags=["ads"], include_in_schema=False)
# Create and include admin router
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from app.db.database import get_async_db
from app.db.models import User, BankRecord, RawExtraction
from app.db.adapter import db as db_adapter

admin_router = APIRouter(prefix="/api/admin", tags=["admin"], include_in_schema=False)

@admin_router.post("/users/{user_id}/disable")
async def disable_user(
    user_id: str,
    current_user: User = Depends(get_current_user_required)
):
    """Disable a user by setting their status to inactive
    
    Args:
        user_id: User ID to disable
        current_user: Current admin user
        
    Returns:
        Success message
    """
    try:
        # Update user status to inactive
        db_adapter.update_user(user_id, {"status": "inactive"})
        
        return {"success": True, "message": f"User {user_id} has been disabled"}
    except Exception as e:
        logger.error(f"Error disabling user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to disable user: {str(e)}")

@admin_router.get("/users", include_in_schema=False)
async def get_users(
    request: Request,
    db = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    """Get all users with their stats"""
    # Check if user is admin
    user_email = get_user_email(current_user)
    if not user_email or not is_admin_email(user_email):
        raise HTTPException(status_code=403, detail="Admin access required")

    try:

        users = db_adapter._db_provider.get_all_users()
        
        # Format the response
        users_list = []
        for user in users:
            # Get counts for each user
            user_id = user.get("id")
            extractions = db_adapter._db_provider.get_raw_extractions_by_user(user_id)
            
            users_list.append({
                "id": user_id,
                "email": user.get("email"),
                "name": user.get("name"),
                "google_id": user.get("google_id"),
                "subscription_tier": user.get("subscription_tier", "FREE").upper(),
                "created_at": user.get("created_at"),
                "last_login": user.get("last_login"),
                "extractions_count": len(extractions),
                "status": user.get("status", "active"),
                "is_admin": is_admin_email(user.get("email", "")) if user.get("email") else False
            })
        
        return users_list
    except Exception as e:
        logger.error(f"Error getting users: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get users: {str(e)}")


@admin_router.get("/stats", include_in_schema=False)
async def get_stats(
    request: Request,
    db = Depends(get_async_db),
    current_user: User = Depends(get_current_user_required)
):
    """Get system statistics"""
    # Check if user is admin
    user_email = get_user_email(current_user)
    if not user_email or not is_admin_email(user_email):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        if db_adapter.db_type != "sqlite":
            # For DynamoDB, use the adapter
            users = db_adapter._db_provider.get_all_users()
            users_count = len(users)
            
            # This is inefficient but works for small datasets
            extractions_count = 0
            for user in users:
                user_id = user.get("id")
                extractions = db_adapter._db_provider.get_raw_extractions_by_user(user_id)
                extractions_count += len(extractions)

        return {
            "users_count": users_count or 0,
            "extractions_count": extractions_count or 0
        }
    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")

# Add endpoint to check if user is admin
@app.get("/api/user/is-admin", include_in_schema=False)
async def check_is_admin(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Check if the current user is an admin"""
    is_admin = False
    if current_user:
        user_email = get_user_email(current_user)
        if user_email:
            is_admin = is_admin_email(user_email)
    return {"is_admin": is_admin}

# Include admin router
app.include_router(admin_router)

# Initialize OAuth
app.state.oauth = oauth

# Page routes
@app.get("/", include_in_schema=False)
async def index(request: Request, current_user: User = Depends(get_current_user)):
    """Main application page - requires authentication"""
    logger.debug("Index route called")
    if not current_user:
        logger.debug("No current user, redirecting to login")
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    logger.debug(f"User authenticated: {get_user_email(current_user)}")
    
    # Get auth token from cookie
    auth_token = request.cookies.get("access_token", "")
    
    # Normalize user data
    user_data = normalize_user_data(current_user)
    
    # Check if user is admin
    is_admin = False
    user_email = get_user_email(current_user)
    if user_email:
        is_admin = is_admin_email(user_email)
        logger.debug(f"User {user_email} is_admin: {is_admin}")
    
    return templates.TemplateResponse(
        "index.html", 
        {
            "request": request, 
            "current_user": user_data,
            "auth_token": auth_token,
            "is_admin": is_admin
        }
    )

@app.get("/login", include_in_schema=False)
async def login_page(request: Request, current_user: User = Depends(get_current_user)):
    """Login page"""
    logger.debug("Login page route called")
    if current_user:
        logger.debug(f"User already authenticated: {get_user_email(current_user)}, redirecting to index")
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    
    logger.debug("Rendering login page")
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/header-config", include_in_schema=False)
async def header_config_page(request: Request, current_user: User = Depends(get_current_user)):
    """Header configuration page - requires authentication"""
    logger.debug("Header config page route called")
    if not current_user:
        logger.debug("No current user, redirecting to login")
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    logger.debug(f"User authenticated: {get_user_email(current_user)}")
    
    # Get auth token from cookie
    auth_token = request.cookies.get("access_token", "")
    
    # Normalize user data
    user_data = normalize_user_data(current_user)
    
    return templates.TemplateResponse(
        "header_config.html", 
        {
            "request": request, 
            "current_user": user_data,
            "auth_token": auth_token
        }
    )

@app.get("/pricing", include_in_schema=False)
async def pricing_page(request: Request, current_user: User = Depends(get_current_user)):
    """Pricing page - requires authentication"""
    logger.debug("Pricing page route called")
    if not current_user:
        logger.debug("No current user, redirecting to login")
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    logger.debug(f"User authenticated: {get_user_email(current_user)}")
    
    # Get auth token from cookie
    auth_token = request.cookies.get("access_token", "")
    
    # Normalize user data
    user_data = normalize_user_data(current_user)
    
    return templates.TemplateResponse(
        "pricing.html", 
        {
            "request": request, 
            "current_user": user_data,
            "auth_token": auth_token
        }
    )

@app.get("/terms", include_in_schema=False)
async def terms_page(request: Request, current_user: User = Depends(get_current_user)):
    """Terms of Service page"""
    logger.debug("Terms of Service page route called")
    
    # Get auth token from cookie if user is authenticated
    auth_token = request.cookies.get("access_token", "") if current_user else ""
    
    # Normalize user data
    user_data = normalize_user_data(current_user) if current_user else None
    
    return templates.TemplateResponse(
        "terms.html", 
        {
            "request": request, 
            "current_user": user_data,
            "auth_token": auth_token
        }
    )

@app.get("/privacy", include_in_schema=False)
async def privacy_page(request: Request, current_user: User = Depends(get_current_user)):
    """Privacy Policy page"""
    logger.debug("Privacy Policy page route called")
    
    # Get auth token from cookie if user is authenticated
    auth_token = request.cookies.get("access_token", "") if current_user else ""
    
    # Normalize user data
    user_data = normalize_user_data(current_user) if current_user else None
    
    return templates.TemplateResponse(
        "privacy.html", 
        {
            "request": request, 
            "current_user": user_data,
            "auth_token": auth_token
        }
    )

# Add admin page route
@app.get("/admin", include_in_schema=False)
async def admin_page(request: Request, current_user: User = Depends(get_current_user)):
    """Admin page - requires admin authentication"""
    logger.debug("Admin page route called")
    if not current_user:
        logger.debug("No current user, redirecting to login")
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    # Get user email (handling both dict and object formats)
    user_email = get_user_email(current_user)
    
    # Check if user is admin
    if not user_email or not is_admin_email(user_email):
        logger.warning(f"Unauthorized admin access attempt by {user_email}")
        raise HTTPException(status_code=403, detail="Admin access required")
    
    logger.debug(f"Admin authenticated: {user_email}")
    
    # Get auth token from cookie
    auth_token = request.cookies.get("access_token", "")
    
    # Normalize user data
    user_data = normalize_user_data(current_user)
    
    return templates.TemplateResponse(
        "admin.html", 
        {
            "request": request, 
            "current_user": user_data,
            "auth_token": auth_token
        }
    )


@app.get("/disabled", include_in_schema=False)
async def disabled(request: Request):
    """
    Render the disabled account page
    
    Args:
        request: FastAPI request
        
    Returns:
        HTML response
    """
    return templates.TemplateResponse("disabled.html", {"request": request})


@app.get("/api-keys", include_in_schema=False)
async def api_keys_page(request: Request, current_user: User = Depends(get_current_user)):
    """API Keys management page"""
    logger.debug("API Keys page route called")
    if not current_user:
        logger.debug("No current user, redirecting to login")
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    # Get auth token from cookie
    auth_token = request.cookies.get("access_token", "")
    
    # Normalize user data
    user_data = normalize_user_data(current_user)
    
    # Check if user is admin
    user_email = get_user_email(current_user)
    is_admin = user_email and is_admin_email(user_email)
    
    return templates.TemplateResponse(
        "api_keys.html", 
        {
            "request": request, 
            "current_user": user_data,
            "auth_token": auth_token,
            "is_admin": is_admin
        }
    )


if __name__ == "__main__":
    logger.info(f"Starting server on {settings.HOST}:{settings.PORT}")
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )