import sys
from app.db.session import engine, SessionLocal
from app.models.config import QueryCache
from app.models.job import Job

db = SessionLocal()

query = '{"q":"Binding of the drug to the EGFR receptor results in the inhibition of the RAS-RAF-MAPK signaling pathway.","n":10000,"end_date":"20000101"}'

print(f"Deleting QueryCache for {query}")
qc = db.query(QueryCache).filter(QueryCache.query_term == query).delete()
print(f"Deleted {qc} QueryCache entries.")

jc = db.query(Job).filter(Job.query_term == query, Job.job_type == "download").delete()
print(f"Deleted {jc} Job entries.")

db.commit()
db.close()
