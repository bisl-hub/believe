from sqlalchemy import create_engine, text
import os
import sys

# Get connection string from env or use default
# docker-compose.yml says:
#   hypothesis-db:
#     image: postgres:15-alpine
#     ...
#     env_file: .env

# I'll try to read .env manually to construct the URL or assume default "postgresql://user:password@localhost:5432/hypothesis_db"
# But the host is 'localhost' if I run from host, assuming port 5432 is exposed.
# The docker-compose said 5432:5432 was commented out? 
# "    #   - "5432:5432" # Removed for internal network isolation"
# Ah, I cannot connect from host if port is not exposed.

# I must run this script INSIDE the backend container.
# or I can use `docker exec -it hypothesis-db psql ...` but that's interactive.
# I can use `docker exec hypothesis-backend python ...`

# Let's assume this script will be run inside the backend container.
# In backend container, DB host is "hypothesis-db".

from app.db.session import SessionLocal
from app.models.job import Job, JobResult
from sqlalchemy import func

def inspect():
    db = SessionLocal()
    try:
        # Get latest job
        job = db.query(Job).order_by(Job.id.desc()).first()
        if not job:
            print("No jobs found")
            return

        print(f"Latest Job ID: {job.id}")
        print(f"Job Status: {job.status}")
        
        # Count results
        total_results = db.query(JobResult).filter(JobResult.job_id == job.id).count()
        print(f"Total Results in DB: {total_results}")
        
        # Group by verdict
        counts = db.query(JobResult.verdict, func.count(JobResult.id)).filter(JobResult.job_id == job.id).group_by(JobResult.verdict).all()
        print("Verdict Distribution:")
        for v, c in counts:
            print(f"  '{v}': {c}")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    inspect()
