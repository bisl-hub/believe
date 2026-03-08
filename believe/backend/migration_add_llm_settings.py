from sqlalchemy import create_engine, text
# from app.db.session import SQLALCHEMY_DATABASE_URL
import os

# Use localhost for migration from host
SQLALCHEMY_DATABASE_URL = "postgresql://user:password@localhost:5432/hypothesis_db"

def migrate():
    print(f"Connecting to database...")
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    
    with engine.connect() as conn:
        with conn.begin():
            print("Checking existing columns in 'jobs' table...")
            
            # Check llm_concurrency_limit
            result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='jobs' AND column_name='llm_concurrency_limit'"))
            if result.fetchone():
                print("Column 'llm_concurrency_limit' already exists. Skipping.")
            else:
                print("Adding column 'llm_concurrency_limit'...")
                conn.execute(text("ALTER TABLE jobs ADD COLUMN llm_concurrency_limit INTEGER DEFAULT 1024"))

            # Check llm_temperature
            result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='jobs' AND column_name='llm_temperature'"))
            if result.fetchone():
                print("Column 'llm_temperature' already exists. Skipping.")
            else:
                print("Adding column 'llm_temperature'...")
                conn.execute(text("ALTER TABLE jobs ADD COLUMN llm_temperature FLOAT DEFAULT 0.0"))

    print("Migration completed successfully.")

if __name__ == "__main__":
    migrate()
