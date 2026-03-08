from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ModelConfigBase(BaseModel):
    project_id: int
    name: str
    openai_api_key: Optional[str] = "bislaprom3#"
    openai_model: Optional[str] = "openai/gpt-oss-120b"
    openai_base_url: Optional[str] = "http://localhost:11433/v1"
    system_prompt: Optional[str] = None
    llm_concurrency_limit: Optional[int] = 1024
    llm_temperature: Optional[float] = 0.0

class ModelConfigCreate(ModelConfigBase):
    pass

class ModelConfigResponse(ModelConfigBase):
    id: int
    owner_id: int
    created_at: datetime

    class Config:
        orm_mode = True

class AnalysisConfigBase(BaseModel):
    project_id: int
    name: str
    hypothesis: str
    default_dataset_id: Optional[int] = None

class AnalysisConfigCreate(AnalysisConfigBase):
    pass

class AnalysisConfigResponse(AnalysisConfigBase):
    id: int
    owner_id: int
    created_at: datetime

    class Config:
        orm_mode = True

class DatasetConfigBase(BaseModel):
    project_id: int
    name: str
    source_type: str
    query: str

class DatasetConfigCreate(DatasetConfigBase):
    pass

class DatasetConfigResponse(DatasetConfigBase):
    id: int
    owner_id: int
    created_at: datetime
    is_downloaded: Optional[bool] = False
    download_job_id: Optional[int] = None
    download_job_status: Optional[str] = None
    progress_text: Optional[str] = None

    class Config:
        orm_mode = True

class QueryCacheResponse(BaseModel):
    id: int
    query_term: str
    pmids: str
    last_updated: datetime

    class Config:
        orm_mode = True
