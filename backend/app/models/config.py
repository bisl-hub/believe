from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Float, Enum
from sqlalchemy.orm import relationship
from ..db import Base
import datetime
import enum

class SourceType(str, enum.Enum):
    TXT_FILE = "txt_file"
    PUBTATOR3 = "pubtator3"
    PUBMED = "pubmed"
    QWEN_RETRIEVER = "qwen_retriever"

class ModelConfig(Base):
    __tablename__ = "model_configs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    
    openai_api_key = Column(String, nullable=True)
    openai_model = Column(String, nullable=True)
    openai_base_url = Column(String, nullable=True)
    system_prompt = Column(Text, nullable=True)
    llm_concurrency_limit = Column(Integer, nullable=True)
    llm_temperature = Column(Float, nullable=True)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    owner = relationship("User")
    project = relationship("Project", back_populates="model_configs")

class AnalysisConfig(Base):
    __tablename__ = "analysis_configs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    default_dataset_id = Column(Integer, ForeignKey("dataset_configs.id"), nullable=True)
    
    # Deprecated: query_term = Column(String) -> Moved to DatasetConfig
    hypothesis = Column(Text)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    owner = relationship("User")
    project = relationship("Project", back_populates="analysis_configs")
    default_dataset = relationship("DatasetConfig")

class DatasetConfig(Base):
    __tablename__ = "dataset_configs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    
    source_type = Column(String, default=SourceType.PUBTATOR3) # "txt_file", "pubtator3", "pubmed"
    query = Column(String) # For "txt_file", this holds comma-separated PMIDs.
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    owner = relationship("User")
    project = relationship("Project", back_populates="dataset_configs")

class QueryCache(Base):
    __tablename__ = "query_cache"

    id = Column(Integer, primary_key=True, index=True)
    query_term = Column(String, index=True, unique=True)
    pmids = Column(Text) # comma-separated list of PMIDs, or JSON structured text
    last_updated = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class ArticleCache(Base):
    __tablename__ = "article_cache"

    pmid = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=True)
    abstract = Column(Text, nullable=True)
    year = Column(String, nullable=True)
    last_updated = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
