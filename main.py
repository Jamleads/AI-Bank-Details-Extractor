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
from app.core.config import settings
from app.db import init_db
from app.services.auth_service import oauth, get_current_user
from app.db.models import User

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
    secret_key=settings.SECRET_KEY
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
    
    logger.debug(f"User authenticated: {current_user.email}")
    return templates.TemplateResponse(
        "index.html", 
        {"request": request, "current_user": current_user}
    )

@app.get("/login")
async def login_page(request: Request, current_user: User = Depends(get_current_user)):
    """Login page"""
    logger.debug("Login page route called")
    if current_user:
        logger.debug(f"User already authenticated: {current_user.email}, redirecting to index")
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    
    logger.debug("Rendering login page")
    return templates.TemplateResponse("login.html", {"request": request})

if __name__ == "__main__":
    logger.info(f"Starting server on {settings.HOST}:{settings.PORT}")
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    ) 