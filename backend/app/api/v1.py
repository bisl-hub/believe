"""
/api/v1/* — Project-scoped public API authenticated via X-Api-Key header.

All endpoints require:
    X-Api-Key: blv_<your_key>

The key identifies the project — no login token needed.
"""
import csv
import hashlib
from datetime import datetime
from io import StringIO
from typing import List, Optional, Union

from fastapi import APIRouter, Header, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import case
from sqlalchemy.orm import Session, defer

from ..db.session import get_db
from ..models import job as job_model
from ..models.config import ModelConfig, AnalysisConfig, DatasetConfig, QueryCache
from ..models.project import Project
from ..models.api_key import ProjectApiKey
from ..schemas import job as job_schema
from ..schemas.config import (
    ModelConfigResponse,
    AnalysisConfigResponse,
    DatasetConfigResponse,
)

# ── v1-specific request bodies (project_id injected from API key) ──────────────

class V1DatasetCreate(BaseModel):
    name: str
    source_type: str
    query: str

class V1ModelConfigCreate(BaseModel):
    name: str
    openai_api_key: Optional[str] = None
    openai_model: Optional[str] = None
    openai_base_url: Optional[str] = None
    system_prompt: Optional[str] = None
    llm_concurrency_limit: Optional[int] = 1024
    llm_temperature: Optional[float] = 0.0

class V1AnalysisConfigCreate(BaseModel):
    name: str
    hypothesis: str
    default_dataset_id: Optional[int] = None
from ..services.docker_service import docker_service

router = APIRouter()


# ── Auth dependency ────────────────────────────────────────────────────────────

def _resolve_project(x_api_key: str = Header(...), db: Session = Depends(get_db)) -> Project:
    hashed = hashlib.sha256(x_api_key.encode()).hexdigest()
    key_row = (
        db.query(ProjectApiKey)
        .filter(ProjectApiKey.key_hash == hashed, ProjectApiKey.is_active == True)
        .first()
    )
    if not key_row:
        raise HTTPException(status_code=401, detail="Invalid or revoked API key")

    key_row.last_used_at = datetime.utcnow()
    db.commit()

    project = db.query(Project).filter(Project.id == key_row.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


# ── Project info ───────────────────────────────────────────────────────────────

class ProjectInfo(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    created_at: datetime

    class Config:
        orm_mode = True


@router.get("/project", response_model=ProjectInfo, summary="Get project info")
def v1_get_project(project: Project = Depends(_resolve_project)):
    """Return basic information about the project this API key belongs to."""
    return project


# ── Dataset Configs ────────────────────────────────────────────────────────────

@router.get("/datasets", response_model=List[DatasetConfigResponse], summary="List dataset configs")
def v1_list_datasets(
    project: Project = Depends(_resolve_project),
    db: Session = Depends(get_db),
):
    """List all dataset configurations for the project."""
    configs = db.query(DatasetConfig).filter(DatasetConfig.project_id == project.id).all()

    download_jobs = (
        db.query(job_model.Job)
        .filter(
            job_model.Job.project_id == project.id,
            job_model.Job.job_type == job_model.JobType.DOWNLOAD,
        )
        .order_by(job_model.Job.created_at.desc())
        .all()
    )
    latest_jobs = {}
    for j in download_jobs:
        if j.query_term not in latest_jobs:
            latest_jobs[j.query_term] = j

    result = []
    for c in configs:
        job = latest_jobs.get(c.query)
        result.append({
            "id": c.id,
            "project_id": c.project_id,
            "owner_id": c.owner_id,
            "created_at": c.created_at,
            "name": c.name,
            "source_type": c.source_type,
            "query": c.query,
            "is_downloaded": bool(job and job.status == job_model.JobStatus.COMPLETED),
            "download_job_id": job.id if job else None,
            "download_job_status": job.status if job else None,
            "progress_text": job.progress_text if job else None,
        })
    return result


@router.post("/datasets", response_model=DatasetConfigResponse, summary="Create dataset config")
def v1_create_dataset(
    body: V1DatasetCreate,
    project: Project = Depends(_resolve_project),
    db: Session = Depends(get_db),
):
    """
    Create a dataset configuration. A DOWNLOAD job is automatically queued to
    pre-fetch PMIDs and abstracts for faster subsequent analysis.

    `source_type` options: `pubtator3`, `pubmed`, `qwen_retriever`, `txt_file`
    """
    new_config = DatasetConfig(**body.dict(), project_id=project.id, owner_id=project.owner_id)
    db.add(new_config)

    existing_job = (
        db.query(job_model.Job)
        .filter(
            job_model.Job.project_id == project.id,
            job_model.Job.job_type == job_model.JobType.DOWNLOAD,
            job_model.Job.query_term == body.query,
            job_model.Job.status.in_([
                job_model.JobStatus.COMPLETED,
                job_model.JobStatus.QUEUED,
                job_model.JobStatus.RUNNING,
            ]),
        )
        .first()
    )

    new_job = None
    if not existing_job:
        new_job = job_model.Job(
            name=f"Pre-Download: {body.name}",
            project_id=project.id,
            query_term=body.query,
            hypothesis="N/A (Download Only Job)",
            max_articles=float("inf"),
            owner_id=project.owner_id,
            status=job_model.JobStatus.QUEUED,
            job_type=job_model.JobType.DOWNLOAD,
            source_type=body.source_type,
            openai_api_key="none",
            openai_model="none",
            openai_base_url="none",
            system_prompt="none",
            llm_concurrency_limit=1,
            llm_temperature=0.0,
        )
        db.add(new_job)

    db.commit()
    db.refresh(new_config)

    ref_job = existing_job or new_job
    return {
        "id": new_config.id,
        "project_id": new_config.project_id,
        "owner_id": new_config.owner_id,
        "created_at": new_config.created_at,
        "name": new_config.name,
        "source_type": new_config.source_type,
        "query": new_config.query,
        "is_downloaded": bool(ref_job and ref_job.status == job_model.JobStatus.COMPLETED),
        "download_job_id": ref_job.id if ref_job else None,
        "download_job_status": ref_job.status if ref_job else None,
        "progress_text": ref_job.progress_text if ref_job else None,
    }


@router.put("/datasets/{config_id}", response_model=DatasetConfigResponse, summary="Update dataset config")
def v1_update_dataset(
    config_id: int,
    body: V1DatasetCreate,
    project: Project = Depends(_resolve_project),
    db: Session = Depends(get_db),
):
    cfg = db.query(DatasetConfig).filter(
        DatasetConfig.id == config_id, DatasetConfig.project_id == project.id
    ).first()
    if not cfg:
        raise HTTPException(status_code=404, detail="Dataset config not found")
    for k, v in body.dict().items():
        setattr(cfg, k, v)
    cfg.project_id = project.id
    db.commit()
    db.refresh(cfg)
    return {"id": cfg.id, "project_id": cfg.project_id, "owner_id": cfg.owner_id,
            "created_at": cfg.created_at, "name": cfg.name, "source_type": cfg.source_type,
            "query": cfg.query, "is_downloaded": False, "download_job_id": None,
            "download_job_status": None, "progress_text": None}


@router.delete("/datasets/{config_id}", summary="Delete dataset config")
def v1_delete_dataset(
    config_id: int,
    project: Project = Depends(_resolve_project),
    db: Session = Depends(get_db),
):
    cfg = db.query(DatasetConfig).filter(
        DatasetConfig.id == config_id, DatasetConfig.project_id == project.id
    ).first()
    if not cfg:
        raise HTTPException(status_code=404, detail="Dataset config not found")

    related_jobs = db.query(job_model.Job).filter(
        job_model.Job.project_id == project.id,
        job_model.Job.query_term == cfg.query,
        job_model.Job.job_type == job_model.JobType.DOWNLOAD,
    ).all()
    for j in related_jobs:
        if j.status == job_model.JobStatus.RUNNING and j.container_id:
            try:
                docker_service.stop_job(j.container_id)
            except Exception:
                pass
        db.delete(j)

    if cfg.query:
        db.query(QueryCache).filter(QueryCache.query_term == cfg.query).delete()

    db.delete(cfg)
    db.commit()
    return {"message": "Deleted"}


@router.post("/datasets/{config_id}/pre-download", summary="Trigger dataset pre-download")
def v1_predownload_dataset(
    config_id: int,
    project: Project = Depends(_resolve_project),
    db: Session = Depends(get_db),
):
    """Queue a job that downloads all PMIDs/abstracts for this dataset query."""
    cfg = db.query(DatasetConfig).filter(
        DatasetConfig.id == config_id, DatasetConfig.project_id == project.id
    ).first()
    if not cfg:
        raise HTTPException(status_code=404, detail="Dataset config not found")

    new_job = job_model.Job(
        name=f"Pre-Download: {cfg.name}",
        project_id=project.id,
        query_term=cfg.query,
        hypothesis="N/A (Download Only Job)",
        max_articles=float("inf"),
        owner_id=project.owner_id,
        status=job_model.JobStatus.QUEUED,
        job_type=job_model.JobType.DOWNLOAD,
        source_type=cfg.source_type,
        openai_api_key="none",
        openai_model="none",
        openai_base_url="none",
        system_prompt="none",
        llm_concurrency_limit=1,
        llm_temperature=0.0,
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    return {"message": "Pre-download job queued", "job_id": new_job.id}


# ── Model Configs ──────────────────────────────────────────────────────────────

@router.get("/model-configs", response_model=List[ModelConfigResponse], summary="List model configs")
def v1_list_model_configs(
    project: Project = Depends(_resolve_project),
    db: Session = Depends(get_db),
):
    """List all LLM model configurations saved for this project."""
    return db.query(ModelConfig).filter(ModelConfig.project_id == project.id).all()


@router.post("/model-configs", response_model=ModelConfigResponse, summary="Create model config")
def v1_create_model_config(
    body: V1ModelConfigCreate,
    project: Project = Depends(_resolve_project),
    db: Session = Depends(get_db),
):
    """
    Save a reusable LLM configuration.

    Fields: `name`, `openai_api_key`, `openai_model`, `openai_base_url`,
    `system_prompt`, `llm_concurrency_limit`, `llm_temperature`
    """
    new = ModelConfig(**body.dict(), project_id=project.id, owner_id=project.owner_id)
    db.add(new)
    db.commit()
    db.refresh(new)
    return new


@router.put("/model-configs/{config_id}", response_model=ModelConfigResponse, summary="Update model config")
def v1_update_model_config(
    config_id: int,
    body: V1ModelConfigCreate,
    project: Project = Depends(_resolve_project),
    db: Session = Depends(get_db),
):
    cfg = db.query(ModelConfig).filter(
        ModelConfig.id == config_id, ModelConfig.project_id == project.id
    ).first()
    if not cfg:
        raise HTTPException(status_code=404, detail="Model config not found")
    for k, v in body.dict().items():
        setattr(cfg, k, v)
    cfg.project_id = project.id
    db.commit()
    db.refresh(cfg)
    return cfg


@router.delete("/model-configs/{config_id}", summary="Delete model config")
def v1_delete_model_config(
    config_id: int,
    project: Project = Depends(_resolve_project),
    db: Session = Depends(get_db),
):
    cfg = db.query(ModelConfig).filter(
        ModelConfig.id == config_id, ModelConfig.project_id == project.id
    ).first()
    if not cfg:
        raise HTTPException(status_code=404, detail="Model config not found")
    db.delete(cfg)
    db.commit()
    return {"message": "Deleted"}


# ── Analysis Configs ───────────────────────────────────────────────────────────

@router.get("/analysis-configs", response_model=List[AnalysisConfigResponse], summary="List analysis configs")
def v1_list_analysis_configs(
    project: Project = Depends(_resolve_project),
    db: Session = Depends(get_db),
):
    """List saved hypothesis/analysis configurations."""
    return db.query(AnalysisConfig).filter(AnalysisConfig.project_id == project.id).all()


@router.post("/analysis-configs", response_model=AnalysisConfigResponse, summary="Create analysis config")
def v1_create_analysis_config(
    body: V1AnalysisConfigCreate,
    project: Project = Depends(_resolve_project),
    db: Session = Depends(get_db),
):
    """Save a reusable analysis configuration (hypothesis + default dataset)."""
    new = AnalysisConfig(**body.dict(), project_id=project.id, owner_id=project.owner_id)
    db.add(new)
    db.commit()
    db.refresh(new)
    return new


@router.put("/analysis-configs/{config_id}", response_model=AnalysisConfigResponse, summary="Update analysis config")
def v1_update_analysis_config(
    config_id: int,
    body: V1AnalysisConfigCreate,
    project: Project = Depends(_resolve_project),
    db: Session = Depends(get_db),
):
    cfg = db.query(AnalysisConfig).filter(
        AnalysisConfig.id == config_id, AnalysisConfig.project_id == project.id
    ).first()
    if not cfg:
        raise HTTPException(status_code=404, detail="Analysis config not found")
    for k, v in body.dict().items():
        setattr(cfg, k, v)
    cfg.project_id = project.id
    db.commit()
    db.refresh(cfg)
    return cfg


@router.delete("/analysis-configs/{config_id}", summary="Delete analysis config")
def v1_delete_analysis_config(
    config_id: int,
    project: Project = Depends(_resolve_project),
    db: Session = Depends(get_db),
):
    cfg = db.query(AnalysisConfig).filter(
        AnalysisConfig.id == config_id, AnalysisConfig.project_id == project.id
    ).first()
    if not cfg:
        raise HTTPException(status_code=404, detail="Analysis config not found")
    db.delete(cfg)
    db.commit()
    return {"message": "Deleted"}


# ── Jobs ───────────────────────────────────────────────────────────────────────

class V1JobCreate(BaseModel):
    name: Optional[str] = None
    query_term: str
    hypothesis: str
    max_articles: float = -1
    max_articles_percent: Optional[float] = None
    source_type: str = "pubtator3"
    openai_api_key: Optional[str] = None
    openai_model: Optional[str] = None
    openai_base_url: Optional[str] = None
    system_prompt: Optional[str] = None
    llm_concurrency_limit: Optional[int] = 1024
    llm_temperature: Optional[float] = 0.0
    model_config_id: Optional[int] = None


@router.post("/jobs", response_model=job_schema.JobResponse, summary="Create analysis job")
def v1_create_job(
    body: V1JobCreate,
    project: Project = Depends(_resolve_project),
    db: Session = Depends(get_db),
):
    """
    Queue a new hypothesis-validation analysis job.

    - Set `max_articles: -1` for unlimited (all PMIDs matching the query).
    - Set `max_articles_percent` (0–100) to sample a percentage instead of a fixed count.
    - Provide `model_config_id` to inherit LLM settings from a saved model config
      (individual fields override the config).
    - `source_type`: `pubtator3` | `pubmed` | `qwen_retriever` | `txt_file`
    """
    api_key = body.openai_api_key
    model = body.openai_model
    base_url = body.openai_base_url
    system_prompt = body.system_prompt
    concurrency = body.llm_concurrency_limit
    temperature = body.llm_temperature

    if body.model_config_id:
        saved = db.query(ModelConfig).filter(
            ModelConfig.id == body.model_config_id,
            ModelConfig.project_id == project.id,
        ).first()
        if not saved:
            raise HTTPException(status_code=404, detail="Model config not found")
        api_key = api_key or saved.openai_api_key
        model = model or saved.openai_model
        base_url = base_url or saved.openai_base_url
        system_prompt = system_prompt or saved.system_prompt
        concurrency = concurrency if concurrency != 1024 else (saved.llm_concurrency_limit or 1024)
        temperature = temperature if temperature != 0.0 else (saved.llm_temperature or 0.0)

    new_job = job_model.Job(
        project_id=project.id,
        name=body.name,
        query_term=body.query_term,
        hypothesis=body.hypothesis,
        max_articles=float("inf") if body.max_articles == -1 else body.max_articles,
        max_articles_percent=body.max_articles_percent,
        owner_id=project.owner_id,
        status=job_model.JobStatus.QUEUED,
        job_type=job_model.JobType.ANALYSIS,
        source_type=body.source_type,
        openai_api_key=api_key,
        openai_model=model,
        openai_base_url=base_url,
        system_prompt=system_prompt,
        llm_concurrency_limit=concurrency,
        llm_temperature=temperature,
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    return new_job


@router.get("/jobs", response_model=job_schema.JobListResponse, summary="List jobs")
def v1_list_jobs(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    project: Project = Depends(_resolve_project),
    db: Session = Depends(get_db),
):
    """
    List analysis jobs for this project (paginated, download jobs excluded).

    `status` filter: `queued` | `running` | `completed` | `failed` | `stopped`
    """
    query = (
        db.query(job_model.Job)
        .filter(
            job_model.Job.project_id == project.id,
            job_model.Job.job_type == job_model.JobType.ANALYSIS,
        )
        .options(
            defer(job_model.Job.logs),
            defer(job_model.Job.result_csv),
            defer(job_model.Job.summary_image),
        )
    )
    if status:
        query = query.filter(job_model.Job.status == status)

    total = query.count()
    jobs = query.order_by(job_model.Job.created_at.desc()).offset((page - 1) * limit).limit(limit).all()

    return {"items": jobs, "total": total, "page": page, "limit": limit,
            "pages": (total + limit - 1) // limit}


@router.get("/jobs/{job_id}", response_model=job_schema.JobResponse, summary="Get job status")
def v1_get_job(
    job_id: int,
    project: Project = Depends(_resolve_project),
    db: Session = Depends(get_db),
):
    """Get the current status and metadata of a job."""
    job = (
        db.query(job_model.Job)
        .options(
            defer(job_model.Job.logs),
            defer(job_model.Job.result_csv),
            defer(job_model.Job.summary_image),
        )
        .filter(job_model.Job.id == job_id, job_model.Job.project_id == project.id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/jobs/{job_id}/stop", summary="Stop a running job")
def v1_stop_job(
    job_id: int,
    project: Project = Depends(_resolve_project),
    db: Session = Depends(get_db),
):
    """Stop a running or queued job."""
    job = db.query(job_model.Job).filter(
        job_model.Job.id == job_id, job_model.Job.project_id == project.id
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status == job_model.JobStatus.RUNNING and job.container_id:
        logs = docker_service.stop_job(job.container_id)
        job.status = job_model.JobStatus.STOPPED
        if logs:
            job.logs = logs
        db.commit()
    return {"message": "Job stopped"}


@router.get("/jobs/{job_id}/logs", summary="Get job logs")
def v1_get_job_logs(
    job_id: int,
    project: Project = Depends(_resolve_project),
    db: Session = Depends(get_db),
):
    """Return the raw log output for a job."""
    job = db.query(job_model.Job).filter(
        job_model.Job.id == job_id, job_model.Job.project_id == project.id
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.logs:
        return {"logs": job.logs}
    if job.container_id:
        logs = docker_service.get_logs(job.container_id)
        if logs:
            return {"logs": logs}
    return {"logs": "No logs available"}


@router.get("/jobs/{job_id}/results", summary="Get job results (paginated JSON)")
def v1_get_job_results(
    job_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=200),
    filter: str = Query("all", description="all | support | reject | neutral"),
    sort_by: str = Query("confidence", description="confidence | year | verdict | pmid | title"),
    order: str = Query("desc", description="asc | desc"),
    project: Project = Depends(_resolve_project),
    db: Session = Depends(get_db),
):
    """
    Return paginated article-level evaluation results for a completed job.

    Each item contains: `pmid`, `title`, `year`, `abstract`, `verdict`,
    `confidence`, `rationale`.
    """
    job = db.query(job_model.Job).filter(
        job_model.Job.id == job_id, job_model.Job.project_id == project.id
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    query = db.query(job_model.JobResult).filter(job_model.JobResult.job_id == job_id)
    if filter != "all":
        query = query.filter(job_model.JobResult.verdict == filter)

    allowed = {
        "confidence": job_model.JobResult.confidence,
        "year": job_model.JobResult.year,
        "verdict": job_model.JobResult.verdict,
        "pmid": job_model.JobResult.pmid,
        "title": job_model.JobResult.title,
    }

    if sort_by == "confidence":
        score_expr = case(
            (job_model.JobResult.confidence.ilike("%high%"), 3),
            (job_model.JobResult.confidence.ilike("%medium%"), 2),
            (job_model.JobResult.confidence.ilike("%low%"), 1),
            else_=0,
        )
        query = query.order_by(score_expr.desc() if order == "desc" else score_expr.asc())
    elif sort_by in allowed:
        col = allowed[sort_by]
        query = query.order_by(col.desc() if order == "desc" else col.asc())

    total = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()

    return {
        "items": [
            {
                "pmid": r.pmid, "title": r.title, "year": r.year,
                "abstract": r.abstract, "verdict": r.verdict,
                "confidence": r.confidence, "rationale": r.rationale,
            }
            for r in items
        ],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit,
    }


@router.get("/jobs/{job_id}/stats", summary="Get verdict summary statistics")
def v1_get_job_stats(
    job_id: int,
    project: Project = Depends(_resolve_project),
    db: Session = Depends(get_db),
):
    """
    Return aggregated verdict counts and a year-by-year breakdown.

    Useful for building charts without downloading all results.
    """
    from sqlalchemy import func

    job = db.query(job_model.Job).filter(
        job_model.Job.id == job_id, job_model.Job.project_id == project.id
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    verdict_counts = (
        db.query(job_model.JobResult.verdict, func.count(job_model.JobResult.id))
        .filter(job_model.JobResult.job_id == job_id)
        .group_by(job_model.JobResult.verdict)
        .all()
    )
    verdict_data = {v: c for v, c in verdict_counts}

    year_rows = (
        db.query(
            job_model.JobResult.year,
            job_model.JobResult.verdict,
            func.count(job_model.JobResult.id),
        )
        .filter(job_model.JobResult.job_id == job_id)
        .group_by(job_model.JobResult.year, job_model.JobResult.verdict)
        .all()
    )
    year_map: dict = {}
    for year, verdict, count in year_rows:
        y = year or "Unknown"
        if y not in year_map:
            year_map[y] = {"year": y, "support": 0, "reject": 0, "neutral": 0}
        if verdict in year_map[y]:
            year_map[y][verdict] += count

    year_data = sorted(year_map.values(), key=lambda d: d["year"])

    return {"verdict_counts": verdict_data, "year_data": year_data}


@router.get("/jobs/{job_id}/csv", summary="Download results as CSV")
def v1_download_csv(
    job_id: int,
    project: Project = Depends(_resolve_project),
    db: Session = Depends(get_db),
):
    """Stream all job results as a CSV file."""
    job = db.query(job_model.Job).filter(
        job_model.Job.id == job_id, job_model.Job.project_id == project.id
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    has_results = (
        db.query(job_model.JobResult)
        .filter(job_model.JobResult.job_id == job_id)
        .first()
    )
    if not has_results:
        if job.result_csv:
            return Response(
                content=job.result_csv,
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=job_{job_id}_results.csv"},
            )
        raise HTTPException(status_code=404, detail="No results available yet")

    from ..db.session import SessionLocal

    def _iter_csv():
        local_db = SessionLocal()
        try:
            buf = StringIO()
            writer = csv.writer(buf)
            writer.writerow(["pmid", "title", "year", "abstract", "verdict", "confidence", "rationale"])
            yield buf.getvalue()
            buf.seek(0); buf.truncate(0)
            offset, chunk = 0, 5000
            while True:
                rows = (
                    local_db.query(job_model.JobResult)
                    .filter(job_model.JobResult.job_id == job_id)
                    .order_by(job_model.JobResult.id)
                    .limit(chunk).offset(offset).all()
                )
                if not rows:
                    break
                for r in rows:
                    writer.writerow([r.pmid, r.title, r.year, r.abstract, r.verdict, r.confidence, r.rationale])
                yield buf.getvalue()
                buf.seek(0); buf.truncate(0)
                offset += chunk
        finally:
            local_db.close()

    return StreamingResponse(
        _iter_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=job_{job_id}_results.csv"},
    )


@router.get("/jobs/{job_id}/image", summary="Download summary chart image")
def v1_get_image(
    job_id: int,
    project: Project = Depends(_resolve_project),
    db: Session = Depends(get_db),
):
    """Return the PNG summary chart generated after job completion."""
    job = db.query(job_model.Job).filter(
        job_model.Job.id == job_id, job_model.Job.project_id == project.id
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.summary_image:
        raise HTTPException(status_code=404, detail="No summary image available")
    return Response(content=job.summary_image, media_type="image/png")
