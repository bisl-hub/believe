from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@db/hypothesis_db")

# Bounded pool with pre-ping so the backend recovers from dropped connections
# and never monopolises Postgres connection slots under concurrent job load.
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=1800,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
