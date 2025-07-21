"""
Web routes for the application
"""
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os
import logging
from pathlib import Path

from app.models.user import UserDB
from app.utils.auth import get_current_user, get_current_user_required
from app.core.admin_config import is_admin_email

# Setup logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create router
router = APIRouter()

# Set up templates
templates_dir = Path(os.path.dirname(os.path.abspath(__file__))) / "templates"
templates = Jinja2Templates(directory=templates_dir)


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, current_user: UserDB = Depends(get_current_user)):
    """
    Render the index page
    
    Args:
        request: FastAPI request
        current_user: Current user (optional)
        
    Returns:
        HTML response
    """
    # If user is not logged in, redirect to login page
    if not current_user:
        return templates.TemplateResponse("login.html", {"request": request})
    
    # Check if user is admin to show admin link
    is_admin = False
    if current_user and current_user.email:
        is_admin = is_admin_email(current_user.email)
        logger.debug(f"User {current_user.email} is_admin: {is_admin}")
    
    return templates.TemplateResponse(
        "index.html", 
        {
            "request": request, 
            "current_user": current_user, 
            "auth_token": request.session.get("auth_token", ""),
            "is_admin": is_admin
        }
    )


@router.get("/login", response_class=HTMLResponse)
async def login(request: Request):
    """
    Render the login page
    
    Args:
        request: FastAPI request
        
    Returns:
        HTML response
    """
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/disabled", response_class=HTMLResponse)
async def disabled(request: Request):
    """
    Render the disabled account page
    
    Args:
        request: FastAPI request
        
    Returns:
        HTML response
    """
    return templates.TemplateResponse("disabled.html", {"request": request})


@router.get("/admin", response_class=HTMLResponse)
async def admin(request: Request, current_user: UserDB = Depends(get_current_user_required)):
    """
    Render the admin page
    
    Args:
        request: FastAPI request
        current_user: Current authenticated user
        
    Returns:
        HTML response
    """
    logger.debug(f"Admin route called by user: {current_user.email if current_user else 'None'}")
    
    # Check if user is admin
    if not current_user or not current_user.email or not is_admin_email(current_user.email):
        logger.warning(f"Unauthorized admin access attempt by {current_user.email if current_user else 'unknown user'}")
        raise HTTPException(status_code=403, detail="Admin access required")
    
    logger.debug(f"Rendering admin template for user: {current_user.email}")
    return templates.TemplateResponse(
        "admin.html", 
        {
            "request": request, 
            "current_user": current_user, 
            "auth_token": request.session.get("auth_token", "")
        }
    ) 