from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Float, LargeBinary
from sqlalchemy.orm import relationship
from ..db import Base
import datetime
import enum

class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"

class JobType(str, enum.Enum):
    ANALYSIS = "analysis"
    DOWNLOAD = "download"

class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=True)
    query_term = Column(String)
    hypothesis = Column(Text)
    max_articles = Column(Float, default=float('inf'))
    status = Column(String, default=JobStatus.QUEUED)
    job_type = Column(String, default=JobType.ANALYSIS)
    source_type = Column(String, default="pubtator3") # "txt_file", "pubtator3", "pubmed"
    container_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    
    # Store outputs directly in DB
    summary_image = Column(LargeBinary, nullable=True)
    result_csv = Column(LargeBinary, nullable=True)
    
    # Custom OpenAI settings
    openai_api_key = Column(String, nullable=True)
    openai_model = Column(String, nullable=True)
    openai_base_url = Column(String, nullable=True)
    system_prompt = Column(Text, nullable=True)
    logs = Column(Text, nullable=True)
    max_articles_percent = Column(Float, nullable=True)
    llm_concurrency_limit = Column(Integer, nullable=True)
    llm_temperature = Column(Float, nullable=True)
    progress_text = Column(String, nullable=True)
    
    owner = relationship("User", back_populates="jobs")
    project = relationship("Project", back_populates="jobs")
    results = relationship("JobResult", back_populates="job")

class JobResult(Base):
    __tablename__ = "job_results"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"))
    pmid = Column(String)
    title = Column(String)
    abstract = Column(Text)
    verdict = Column(String)
    confidence = Column(String)
    rationale = Column(Text)
    year = Column(String)
    
    job = relationship("Job", back_populates="results")
