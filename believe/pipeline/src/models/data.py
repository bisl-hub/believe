from dataclasses import dataclass
from sqlalchemy import Column, Integer, String, Text, Float, LargeBinary, DateTime
from sqlalchemy.orm import declarative_base

@dataclass(frozen=True)
class Article:
    pmid: str
    title: str
    abstract: str
    year: str

@dataclass(frozen=True)
class ArticleEvaluation:
    pmid: str
    title: str
    abstract: str
    year: str
    hypothesis: str
    verdict: str
    confidence: str
    rationale: str

Base = declarative_base()

class JobResult(Base):
    __tablename__ = "job_results"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, index=True)
    pmid = Column(String)
    title = Column(String)
    abstract = Column(Text)
    verdict = Column(String)
    confidence = Column(String)
    rationale = Column(Text)
    year = Column(String)

class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    query_term = Column(String, index=True)
    hypothesis = Column(Text)
    status = Column(String, default="pending")
    result_csv = Column(LargeBinary, nullable=True)
    summary_image = Column(LargeBinary, nullable=True)

class QueryCache(Base):
    __tablename__ = "query_cache"

    id = Column(Integer, primary_key=True, index=True)
    query_term = Column(String, index=True, unique=True)
    pmids = Column(Text)

class ArticleCache(Base):
    __tablename__ = "article_cache"

    pmid = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=True)
    abstract = Column(Text, nullable=True)
    year = Column(String, nullable=True)
