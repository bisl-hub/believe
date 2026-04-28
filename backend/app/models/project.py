from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship
from ..db import Base
import datetime

class ProjectUser(Base):
    __tablename__ = "project_users"
    
    project_id = Column(Integer, ForeignKey("projects.id"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    joined_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # We could add 'role' here later if we want admin vs viewer permissions
    
    project = relationship("Project", back_populates="members")
    user = relationship("User", back_populates="project_links")

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String, nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    owner = relationship("User", back_populates="owned_projects")
    members = relationship("ProjectUser", back_populates="project", cascade="all, delete-orphan")
    
    # These will be mapped from the other models using back_populates
    jobs = relationship("Job", back_populates="project", cascade="all, delete-orphan")
    dataset_configs = relationship("DatasetConfig", back_populates="project", cascade="all, delete-orphan")
    analysis_configs = relationship("AnalysisConfig", back_populates="project", cascade="all, delete-orphan")
    model_configs = relationship("ModelConfig", back_populates="project", cascade="all, delete-orphan")
    api_keys = relationship("ProjectApiKey", back_populates="project", cascade="all, delete-orphan")
