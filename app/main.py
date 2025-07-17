from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
from pathlib import Path

from app.api.routes import router as api_router
from app.api.auth import router as auth_router
from app.api.drive import router as drive_router
from app.api.admin import router as admin_router
from app.routes import router as web_router

# Create FastAPI app
app = FastAPI()

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_dir = Path(os.path.dirname(os.path.abspath(__file__))) / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Include routers
app.include_router(api_router, prefix="/api")
app.include_router(auth_router, prefix="/auth")
app.include_router(drive_router)
app.include_router(admin_router, prefix="/api")
app.include_router(web_router) 