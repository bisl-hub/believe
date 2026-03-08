from sqlalchemy.orm import declarative_base
from .session import engine, SessionLocal, get_db

Base = declarative_base()
