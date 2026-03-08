from pydantic import BaseModel, validator
from typing import Optional
from datetime import datetime

class JobCreate(BaseModel):
    project_id: int
    name: Optional[str] = None
    query_term: str
    hypothesis: str
    max_articles: float = float('inf')
    max_articles_percent: Optional[float] = None
    job_type: str = "analysis"
    source_type: str = "pubtator3"
    openai_api_key: Optional[str] = "bislaprom3#"
    openai_model: Optional[str] = "openai/gpt-oss-120b"
    openai_base_url: Optional[str] = "http://localhost:11433/v1"
    system_prompt: Optional[str] = None
    llm_concurrency_limit: Optional[int] = 1024
    llm_temperature: Optional[float] = 0.0

class JobResponse(BaseModel):
    id: int
    project_id: Optional[int] = None
    name: Optional[str]
    query_term: str
    hypothesis: str
    max_articles: float
    max_articles_percent: Optional[float]
    status: str
    job_type: str
    source_type: str
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    owner_id: int
    openai_api_key: Optional[str]
    openai_model: Optional[str]
    openai_base_url: Optional[str]
    system_prompt: Optional[str]
    system_prompt: Optional[str]
    llm_concurrency_limit: Optional[int] = None
    llm_temperature: Optional[float] = None
    progress_text: Optional[str] = None
    
    @validator('max_articles', pre=True, always=True)
    def handle_infinity(cls, v):
        if v == float('inf'):
            return -1.0
        return v

    class Config:
        orm_mode = True

class JobListResponse(BaseModel):
    items: list[JobResponse]
    total: int
    page: int
    limit: int
    pages: int
