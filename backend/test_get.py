import sys
import json
from app.db.session import SessionLocal
from app.models.job import Job
from app.schemas.job import JobResponse
from sqlalchemy.orm import defer

db = SessionLocal()
job = db.query(Job).options(
    defer(Job.logs),
    defer(Job.result_csv),
    defer(Job.summary_image)
).filter(Job.id == 368).first()

if job:
    schema = JobResponse.from_orm(job)
    print(schema.json())
else:
    print("Job not found")
