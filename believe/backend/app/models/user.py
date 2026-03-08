from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from ..db import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Integer, default=1)
    
    jobs = relationship("Job", back_populates="owner")
    owned_projects = relationship("Project", back_populates="owner")
    project_links = relationship("ProjectUser", back_populates="user", cascade="all, delete-orphan")
