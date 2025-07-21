"""
Database initialization
"""
import logging
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.database import Base
from app.db.adapter import db

logger = logging.getLogger(__name__)


async def init_db():
    """Initialize database"""
    if settings.DATABASE_TYPE == "sqlite":
        # Initialize SQLite database
        logger.info("Initializing SQLite database")
        from sqlalchemy.ext.asyncio import create_async_engine
        
        # Create async engine
        engine = create_async_engine(
            f"sqlite+aiosqlite:///{settings.DATABASE_PATH}",
            echo=settings.DEBUG,
            future=True
        )
        
        # Create tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)