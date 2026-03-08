import sys
import os
from sqlalchemy import create_engine, text

# Get DB URL from env or use default
SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://postgres:postgres@localhost:5433/hypothesis_db" # default for local script
)

print(f"Connecting to {SQLALCHEMY_DATABASE_URL}...")
engine = create_engine(SQLALCHEMY_DATABASE_URL)

with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE jobs ADD COLUMN progress_text VARCHAR;"))
        conn.commit()
        print("Successfully added progress_text column to jobs table.")
    except Exception as e:
        print(f"Error (might already exist): {e}")

