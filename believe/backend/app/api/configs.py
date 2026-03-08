from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List

from ..db.session import get_db
from ..models import config as config_models
from ..models import user as user_model
from ..models import job as job_model
from ..models.project import ProjectUser
from ..schemas import config as config_schema
from .users import get_current_user
from ..services.docker_service import docker_service
from datetime import datetime

router = APIRouter()

def check_project_access(project_id: int, user_id: int, db: Session):
    is_member = db.query(ProjectUser).filter(ProjectUser.project_id == project_id, ProjectUser.user_id == user_id).first()
    if not is_member:
        raise HTTPException(status_code=403, detail="Not a member of this project")

# --- Model Config Endpoints ---

@router.post("/model", response_model=config_schema.ModelConfigResponse)
def create_model_config(
    config: config_schema.ModelConfigCreate, 
    current_user: user_model.User = Depends(get_current_user), 
    db: Session = Depends(get_db)):
    
    check_project_access(config.project_id, current_user.id, db)
    new_config = config_models.ModelConfig(**config.dict(), owner_id=current_user.id)
    db.add(new_config)
    db.commit()
    db.refresh(new_config)
    return new_config

@router.get("/model", response_model=List[config_schema.ModelConfigResponse])
def get_model_configs(
    project_id: int,
    current_user: user_model.User = Depends(get_current_user), 
    db: Session = Depends(get_db)):
    
    check_project_access(project_id, current_user.id, db)
    return db.query(config_models.ModelConfig).filter(config_models.ModelConfig.project_id == project_id).all()

@router.put("/model/{config_id}", response_model=config_schema.ModelConfigResponse)
def update_model_config(
    config_id: int, 
    config: config_schema.ModelConfigCreate, 
    current_user: user_model.User = Depends(get_current_user), 
    db: Session = Depends(get_db)):
    
    db_config = db.query(config_models.ModelConfig).filter(config_models.ModelConfig.id == config_id).first()
    if not db_config:
        raise HTTPException(status_code=404, detail="Model config not found")
        
    check_project_access(db_config.project_id, current_user.id, db)
    check_project_access(config.project_id, current_user.id, db)
        
    for key, value in config.dict().items():
        setattr(db_config, key, value)
        
    db.commit()
    db.refresh(db_config)
    return db_config

@router.delete("/model/{config_id}")
def delete_model_config(
    config_id: int, 
    current_user: user_model.User = Depends(get_current_user), 
    db: Session = Depends(get_db)):
    
    config = db.query(config_models.ModelConfig).filter(config_models.ModelConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Model config not found")
        
    check_project_access(config.project_id, current_user.id, db)
    db.delete(config)
    db.commit()
    return {"message": "Deleted"}

# --- Analysis Config Endpoints ---

@router.post("/analysis", response_model=config_schema.AnalysisConfigResponse)
def create_analysis_config(
    config: config_schema.AnalysisConfigCreate, 
    current_user: user_model.User = Depends(get_current_user), 
    db: Session = Depends(get_db)):
    
    check_project_access(config.project_id, current_user.id, db)
    new_config = config_models.AnalysisConfig(**config.dict(), owner_id=current_user.id)
    db.add(new_config)
    db.commit()
    db.refresh(new_config)
    return new_config

@router.get("/analysis", response_model=List[config_schema.AnalysisConfigResponse])
def get_analysis_configs(
    project_id: int,
    current_user: user_model.User = Depends(get_current_user), 
    db: Session = Depends(get_db)):
    
    check_project_access(project_id, current_user.id, db)
    return db.query(config_models.AnalysisConfig).filter(config_models.AnalysisConfig.project_id == project_id).all()

@router.put("/analysis/{config_id}", response_model=config_schema.AnalysisConfigResponse)
def update_analysis_config(
    config_id: int, 
    config: config_schema.AnalysisConfigCreate, 
    current_user: user_model.User = Depends(get_current_user), 
    db: Session = Depends(get_db)):
    
    db_config = db.query(config_models.AnalysisConfig).filter(config_models.AnalysisConfig.id == config_id).first()
    if not db_config:
        raise HTTPException(status_code=404, detail="Analysis config not found")
        
    check_project_access(db_config.project_id, current_user.id, db)
    check_project_access(config.project_id, current_user.id, db)
        
    for key, value in config.dict().items():
        setattr(db_config, key, value)
        
    db.commit()
    db.refresh(db_config)
    return db_config

@router.delete("/analysis/{config_id}")
def delete_analysis_config(
    config_id: int, 
    current_user: user_model.User = Depends(get_current_user), 
    db: Session = Depends(get_db)):
    
    config = db.query(config_models.AnalysisConfig).filter(config_models.AnalysisConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Analysis config not found")
        
    check_project_access(config.project_id, current_user.id, db)
    db.delete(config)
    db.commit()
    return {"message": "Deleted"}

# --- Dataset Config Endpoints ---

@router.post("/datasets", response_model=config_schema.DatasetConfigResponse)
def create_dataset_config(
    config: config_schema.DatasetConfigCreate, 
    current_user: user_model.User = Depends(get_current_user), 
    db: Session = Depends(get_db)):
    
    check_project_access(config.project_id, current_user.id, db)
    new_config = config_models.DatasetConfig(**config.dict(), owner_id=current_user.id)
    db.add(new_config)
    
    existing_job = db.query(job_model.Job).filter(
        job_model.Job.project_id == config.project_id,
        job_model.Job.job_type == job_model.JobType.DOWNLOAD,
        job_model.Job.query_term == config.query,
        job_model.Job.status.in_([job_model.JobStatus.COMPLETED, job_model.JobStatus.QUEUED, job_model.JobStatus.RUNNING])
    ).first()

    if not existing_job:
        new_job = job_model.Job(
            name=f"Pre-Download: {config.name}",
            project_id=config.project_id,
            query_term=config.query,
            hypothesis="N/A (Download Only Job)",
            max_articles=float('inf'), # Download everything matching query
            owner_id=current_user.id,
            status=job_model.JobStatus.QUEUED,
            job_type=job_model.JobType.DOWNLOAD,
            source_type=config.source_type,
            openai_api_key="none",
            openai_model="none",
            openai_base_url="none",
            system_prompt="none",
            llm_concurrency_limit=1,
            llm_temperature=0.0
        )
        db.add(new_job)

    db.commit()
    db.refresh(new_config)
    
    # We populate these right after creation based on what we just did
    if existing_job:
        new_config.download_job_id = existing_job.id
        new_config.download_job_status = existing_job.status
        new_config.is_downloaded = (existing_job.status == job_model.JobStatus.COMPLETED)
        new_config.progress_text = existing_job.progress_text
    else:
        new_config.download_job_id = new_job.id
        new_config.download_job_status = new_job.status
        new_config.is_downloaded = False
        new_config.progress_text = None
        
    return new_config

@router.get("/datasets", response_model=List[config_schema.DatasetConfigResponse])
def get_dataset_configs(
    project_id: int,
    current_user: user_model.User = Depends(get_current_user), 
    db: Session = Depends(get_db)):
    
    check_project_access(project_id, current_user.id, db)
    configs = db.query(config_models.DatasetConfig).filter(config_models.DatasetConfig.project_id == project_id).all()
    
    download_jobs = db.query(job_model.Job).filter(
        job_model.Job.project_id == project_id,
        job_model.Job.job_type == job_model.JobType.DOWNLOAD
    ).order_by(job_model.Job.created_at.desc()).all()
    
    latest_jobs = {}
    for j in download_jobs:
        if j.query_term not in latest_jobs:
            latest_jobs[j.query_term] = j
            
    response_list = []
    for c in configs:
        job = latest_jobs.get(c.query)
        # Create a dict from the config to avoid Pydantic dropping dynamically added fields
        c_dict = {
            "id": c.id,
            "project_id": c.project_id,
            "owner_id": c.owner_id,
            "created_at": c.created_at,
            "name": c.name,
            "source_type": c.source_type,
            "query": c.query,
            "is_downloaded": False,
            "download_job_id": None,
            "download_job_status": None,
            "progress_text": None
        }
        
        if job:
            c_dict["download_job_id"] = job.id
            c_dict["download_job_status"] = job.status
            c_dict["is_downloaded"] = (job.status == job_model.JobStatus.COMPLETED)
            c_dict["progress_text"] = job.progress_text
            
        response_list.append(c_dict)
        
    return response_list

@router.put("/datasets/{config_id}", response_model=config_schema.DatasetConfigResponse)
def update_dataset_config(
    config_id: int, 
    config: config_schema.DatasetConfigCreate, 
    current_user: user_model.User = Depends(get_current_user), 
    db: Session = Depends(get_db)):
    
    db_config = db.query(config_models.DatasetConfig).filter(config_models.DatasetConfig.id == config_id).first()
    if not db_config:
        raise HTTPException(status_code=404, detail="Dataset config not found")
        
    check_project_access(db_config.project_id, current_user.id, db)
    check_project_access(config.project_id, current_user.id, db)
        
    for key, value in config.dict().items():
        setattr(db_config, key, value)
        
    existing_job = db.query(job_model.Job).filter(
        job_model.Job.project_id == config.project_id,
        job_model.Job.job_type == job_model.JobType.DOWNLOAD,
        job_model.Job.query_term == config.query,
        job_model.Job.status.in_([job_model.JobStatus.COMPLETED, job_model.JobStatus.QUEUED, job_model.JobStatus.RUNNING])
    ).first()

    if not existing_job:
        new_job = job_model.Job(
            name=f"Pre-Download: {config.name}",
            project_id=config.project_id,
            query_term=config.query,
            hypothesis="N/A (Download Only Job)",
            max_articles=float('inf'), 
            owner_id=current_user.id,
            status=job_model.JobStatus.QUEUED,
            job_type=job_model.JobType.DOWNLOAD,
            source_type=config.source_type,
            openai_api_key="none",
            openai_model="none",
            openai_base_url="none",
            system_prompt="none",
            llm_concurrency_limit=1,
            llm_temperature=0.0
        )
        db.add(new_job)

    db.commit()
    db.refresh(db_config)
    
    if existing_job:
        db_config.download_job_id = existing_job.id
        db_config.download_job_status = existing_job.status
        db_config.is_downloaded = (existing_job.status == job_model.JobStatus.COMPLETED)
        db_config.progress_text = existing_job.progress_text
    else:
        db_config.download_job_id = new_job.id
        db_config.download_job_status = new_job.status
        db_config.is_downloaded = False
        db_config.progress_text = None
        
    return db_config

@router.delete("/datasets/{config_id}")
def delete_dataset_config(
    config_id: int, 
    current_user: user_model.User = Depends(get_current_user), 
    db: Session = Depends(get_db)):
    
    config = db.query(config_models.DatasetConfig).filter(config_models.DatasetConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Dataset config not found")
        
    check_project_access(config.project_id, current_user.id, db)
        
    # Find active download jobs for this dataset's query
    active_jobs = db.query(job_model.Job).filter(
        job_model.Job.project_id == config.project_id,
        job_model.Job.query_term == config.query,
        job_model.Job.job_type == job_model.JobType.DOWNLOAD,
        job_model.Job.status.in_([job_model.JobStatus.RUNNING, job_model.JobStatus.QUEUED])
    ).all()
    
    for job in active_jobs:
        if job.status == job_model.JobStatus.RUNNING and job.container_id:
            try:
                docker_service.stop_job(job.container_id)
            except Exception as e:
                print(f"Error stopping container for job {job.id}: {e}")
        
        job.status = job_model.JobStatus.STOPPED
        job.finished_at = datetime.utcnow()
    
    db.delete(config)
    db.commit()
    return {"message": "Deleted"}

@router.post("/datasets/{config_id}/pre-download")
def pre_download_dataset_data(
    config_id: int, 
    current_user: user_model.User = Depends(get_current_user), 
    db: Session = Depends(get_db)):
    
    config = db.query(config_models.DatasetConfig).filter(config_models.DatasetConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Dataset config not found")
        
    check_project_access(config.project_id, current_user.id, db)
        
    # Create new job in QUEUED state for downloading
    new_job = job_model.Job(
        name=f"Pre-Download: {config.name}",
        project_id=config.project_id,
        query_term=config.query,
        hypothesis="N/A (Download Only Job)",
        max_articles=float('inf'), # Download everything matching query
        owner_id=current_user.id,
        status=job_model.JobStatus.QUEUED,
        job_type=job_model.JobType.DOWNLOAD,
        source_type=config.source_type,
        openai_api_key="none",
        openai_model="none",
        openai_base_url="none",
        system_prompt="none",
        llm_concurrency_limit=1,
        llm_temperature=0.0
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    
    return {"message": "Pre-download Job created.", "job_id": new_job.id}

@router.post("/datasets/{config_id}/force_download")
def force_download_dataset_data(
    config_id: int, 
    current_user: user_model.User = Depends(get_current_user), 
    db: Session = Depends(get_db)):
    
    config = db.query(config_models.DatasetConfig).filter(config_models.DatasetConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Dataset config not found")
        
    check_project_access(config.project_id, current_user.id, db)
        
    # Create new job in QUEUED state for downloading
    new_job = job_model.Job(
        name=f"Force-Download: {config.name}",
        project_id=config.project_id,
        query_term=config.query,
        hypothesis="N/A (Download Only Job)",
        max_articles=float('inf'), # Download everything matching query
        owner_id=current_user.id,
        status=job_model.JobStatus.QUEUED,
        job_type=job_model.JobType.DOWNLOAD,
        source_type=config.source_type,
        openai_api_key="none",
        openai_model="none",
        openai_base_url="none",
        system_prompt="none",
        llm_concurrency_limit=1,
        llm_temperature=0.0
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    
    return {"message": "Force-download Job created.", "job_id": new_job.id}
