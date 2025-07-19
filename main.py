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
from app.core.config import settings
from app.db import init_db
from app.services.auth_service import oauth, get_current_user
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
    title="Bank Details Extractor",
    description="Extract bank details from PDF documents using Gemini AI",
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

# Create and include admin router
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from app.db.database import get_async_db
from app.db.models import User, BankRecord, RawExtraction
from app.db.adapter import db as db_adapter

admin_router = APIRouter(prefix="/api/admin", tags=["admin"])

@admin_router.get("/users")
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
        # For DynamoDB users, we'll use a different approach
        if db_adapter.db_type != "sqlite":
            # Get all users from DynamoDB
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
                    "is_admin": is_admin_email(user.get("email", "")) if user.get("email") else False
                })
            
            return users_list
        
        # For SQLite, use raw SQL to avoid enum issues
        query = """
            SELECT 
                u.id, u.email, u.google_id, u.name, u.picture, 
                u.created_at, u.last_login, u.subscription_tier,
                u.subscription_updated_at,
                COUNT(DISTINCT b.id) as bank_records_count,
                COUNT(DISTINCT r.id) as extractions_count
            FROM 
                users u
            LEFT JOIN 
                bank_records b ON u.id = b.user_id
            LEFT JOIN 
                raw_extractions r ON u.id = r.user_id
            GROUP BY 
                u.id
        """
        
        result = await db.execute(query)
        rows = await result.fetchall()
        
        # Format the response
        users_list = []
        for row in rows:
            # Convert subscription_tier to uppercase if it's a string
            subscription_tier = row[7]  # subscription_tier is at index 7
            if isinstance(subscription_tier, str):
                subscription_tier = subscription_tier.upper()
            
            users_list.append({
                "id": row[0],
                "email": row[1],
                "name": row[3],
                "google_id": row[2],
                "subscription_tier": subscription_tier,
                "created_at": row[5].isoformat() if row[5] else None,
                "last_login": row[6].isoformat() if row[6] else None,
                "bank_records_count": row[9],
                "extractions_count": row[10],
                "is_admin": is_admin_email(row[1]) if row[1] else False
            })
        
        return users_list
    except Exception as e:
        logger.error(f"Error getting users: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get users: {str(e)}")

@admin_router.get("/stats")
async def get_stats(
    request: Request,
    db = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
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
@app.get("/api/user/is-admin")
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
@app.get("/")
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

@app.get("/login")
async def login_page(request: Request, current_user: User = Depends(get_current_user)):
    """Login page"""
    logger.debug("Login page route called")
    if current_user:
        logger.debug(f"User already authenticated: {get_user_email(current_user)}, redirecting to index")
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    
    logger.debug("Rendering login page")
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/header-config")
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

@app.get("/pricing")
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

@app.get("/terms")
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

@app.get("/privacy")
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
@app.get("/admin")
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

if __name__ == "__main__":
    logger.info(f"Starting server on {settings.HOST}:{settings.PORT}")
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )