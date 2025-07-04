"""
Database package initialization
"""
from app.db.database import Base, engine, get_db
from app.db.models import User, BankRecord


async def init_db():
    """Initialize database"""
    async with engine.begin() as conn:
        # Create tables
        await conn.run_sync(Base.metadata.create_all) 