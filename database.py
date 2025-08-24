"""
Database initialization module to avoid circular imports
"""
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

# Create the database instance that will be shared across the application
db = SQLAlchemy(model_class=Base)
