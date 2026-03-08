from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import case
from typing import List
from datetime import datetime
import time
from fastapi.responses import Response, StreamingResponse
import csv
from io import StringIO

from ..db.session import get_db
from ..models import job as job_model
from ..models import user as user_model
from ..models.project import ProjectUser
from ..schemas import job as job_schema
from ..services.docker_service import docker_service
from .users import get_current_user
import docker

router = APIRouter()

@router.post("", response_model=job_schema.JobResponse)
def create_job(job: job_schema.JobCreate, background_tasks: BackgroundTasks, current_user: user_model.User = Depends(get_current_user), db: Session = Depends(get_db)):
    is_member = db.query(ProjectUser).filter(ProjectUser.project_id == job.project_id, ProjectUser.user_id == current_user.id).first()
    if not is_member:
        raise HTTPException(status_code=403, detail="Not a member of this project")

    # Create new job in QUEUED state
    new_job = job_model.Job(
        project_id=job.project_id,
        name=job.name,
        query_term=job.query_term,
        hypothesis=job.hypothesis,
        max_articles=float('inf') if job.max_articles == -1 else job.max_articles,
        owner_id=current_user.id,
        status=job_model.JobStatus.QUEUED,
        job_type=job.job_type,
        openai_api_key=job.openai_api_key,
        openai_model=job.openai_model,
        openai_base_url=job.openai_base_url,
        system_prompt=job.system_prompt,
        max_articles_percent=job.max_articles_percent,
        llm_concurrency_limit=job.llm_concurrency_limit,
        llm_temperature=job.llm_temperature
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    
    # QueueManager running in background will pick this up automatically
    # No need to trigger anything explicitly here
    
    return new_job

from typing import List, Union

@router.get("", response_model=Union[job_schema.JobListResponse, List[job_schema.JobResponse]])
def get_jobs(project_id: int, exclude_download: bool = True, page: int = None, limit: int = None, current_user: user_model.User = Depends(get_current_user), db: Session = Depends(get_db)):
    from sqlalchemy.orm import defer
    
    is_member = db.query(ProjectUser).filter(ProjectUser.project_id == project_id, ProjectUser.user_id == current_user.id).first()
    if not is_member:
        raise HTTPException(status_code=403, detail="Not a member of this project")
    
    # Legacy support: if no page/limit provided (e.g. cached frontend), return list
    if page is None and limit is None:
        jobs = db.query(job_model.Job)\
            .filter(job_model.Job.project_id == project_id)\
            .options(
                defer(job_model.Job.logs),
                defer(job_model.Job.result_csv),
                defer(job_model.Job.summary_image)
            )\
            .order_by(job_model.Job.created_at.desc())\
            .limit(100)\
            .all()
        return jobs

    # New implementation with pagination
    current_page = page or 1
    current_limit = limit or 10
    
    skip = (current_page - 1) * current_limit
    
    query = db.query(job_model.Job).filter(job_model.Job.project_id == project_id)
    if exclude_download:
        query = query.filter(job_model.Job.job_type != job_model.JobType.DOWNLOAD)
        
    total = query.count()
    
    # Defer heavy columns to avoid loading large data (CSV, Logs, Images) for simple list
    jobs = query.options(
            defer(job_model.Job.logs),
            defer(job_model.Job.result_csv),
            defer(job_model.Job.summary_image)
        )\
        .order_by(job_model.Job.created_at.desc())\
        .offset(skip)\
        .limit(current_limit)\
        .all()
    
    return {
        "items": jobs,
        "total": total,
        "page": current_page,
        "limit": current_limit,
        "pages": (total + current_limit - 1) // current_limit
    }

@router.get("/{job_id}", response_model=job_schema.JobResponse)
def get_job(job_id: int, current_user: user_model.User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.query(job_model.Job).filter(job_model.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    is_member = db.query(ProjectUser).filter(ProjectUser.project_id == job.project_id, ProjectUser.user_id == current_user.id).first()
    if not is_member:
        raise HTTPException(status_code=403, detail="Not a member of this project")
        
    return job

@router.post("/{job_id}/stop")
def stop_job(job_id: int, current_user: user_model.User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.query(job_model.Job).filter(job_model.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status == job_model.JobStatus.RUNNING and job.container_id:
        logs = docker_service.stop_job(job.container_id)
        job.status = job_model.JobStatus.STOPPED
        if logs:
            job.logs = logs
        db.commit()
    
    return {"message": "Job canceled"}

@router.delete("/{job_id}")
def delete_job(job_id: int, current_user: user_model.User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.query(job_model.Job).filter(job_model.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Stop container if running
    if job.status == job_model.JobStatus.RUNNING and job.container_id:
        try:
            docker_service.stop_job(job.container_id)
        except Exception as e:
            print(f"Error stopping container for job {job_id}: {e}")
    
    # Delete job results
    db.query(job_model.JobResult).filter(job_model.JobResult.job_id == job_id).delete()
    
    # Delete job
    db.delete(job)
    db.commit()
    
    return {"message": "Job deleted"}

@router.get("/{job_id}/logs")
def get_job_logs(job_id: int, current_user: user_model.User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.query(job_model.Job).filter(job_model.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.logs:
        return {"logs": job.logs}
    
    if job.container_id:
        logs = docker_service.get_logs(job.container_id)
        if logs is not None:
            return {"logs": logs}
    
    return {"logs": "No logs available or container not running."}

@router.get("/{job_id}/results")
def get_job_results(
    job_id: int, 
    page: int = 1, 
    limit: int = 10, 
    filter: str = "all",
    sort_by: str = "confidence",
    order: str = "desc",
    current_user: user_model.User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):

    query = db.query(job_model.JobResult).filter(job_model.JobResult.job_id == job_id)
    
    if filter != "all":
        query = query.filter(job_model.JobResult.verdict == filter)
    
    # Validate and apply sorting
    allowed_sort_fields = {
        "confidence": job_model.JobResult.confidence,
        "year": job_model.JobResult.year,
        "verdict": job_model.JobResult.verdict,
        "pmid": job_model.JobResult.pmid,
        "title": job_model.JobResult.title
    }
    
    if sort_by == "confidence":
        # Custom sorting for High/Medium/Low
        # Map High->3, Medium->2, Low->1, others->0 (or parse float if possible? No, keep it simple)
        # If it's a number string, this might not sort numerically correct (e.g. "10" < "2"). 
        # But user agreed to string sort or custom. Let's try to handle H/M/L specifically.
        confidence_score = case(
            (job_model.JobResult.confidence.ilike("%high%"), 3),
            (job_model.JobResult.confidence.ilike("%medium%"), 2),
            (job_model.JobResult.confidence.ilike("%low%"), 1),
            else_=0
        )
        if order.lower() == "asc":
            query = query.order_by(confidence_score.asc(), job_model.JobResult.confidence.asc())
        else:
            query = query.order_by(confidence_score.desc(), job_model.JobResult.confidence.desc())
            
    elif sort_by in allowed_sort_fields:
        sort_column = allowed_sort_fields[sort_by]
        if order.lower() == "asc":
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())
    else:
        # Default sorting by confidence descending (using custom logic)
        confidence_score = case(
            (job_model.JobResult.confidence.ilike("%high%"), 3),
            (job_model.JobResult.confidence.ilike("%medium%"), 2),
            (job_model.JobResult.confidence.ilike("%low%"), 1),
            else_=0
        )
        query = query.order_by(confidence_score.desc(), job_model.JobResult.confidence.desc())
    
    total = query.count()
    results = query.offset((page - 1) * limit).limit(limit).all()
    
    return {
        "items": results,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit
    }

@router.get("/{job_id}/stats")
def get_job_stats(job_id: int, current_user: user_model.User = Depends(get_current_user), db: Session = Depends(get_db)):
    from sqlalchemy import func

    
    # Verdict counts
    verdict_counts = db.query(job_model.JobResult.verdict, func.count(job_model.JobResult.id)).filter(job_model.JobResult.job_id == job_id).group_by(job_model.JobResult.verdict).all()
    verdict_data = {v: c for v, c in verdict_counts}
    
    # Dynamic Sync: If this is a DOWNLOAD job, its true cached size might have expanded during a subsequent ANALYSIS job.
    job = db.query(job_model.Job).filter(job_model.Job.id == job_id).first()
    if job and job.job_type == job_model.JobType.DOWNLOAD:
        max_count = 0
        related_job_ids = db.query(job_model.Job.id).filter(job_model.Job.query_term == job.query_term).all()
        for (jid,) in related_job_ids:
            c = db.query(func.count(job_model.JobResult.id)).filter(job_model.JobResult.job_id == jid).scalar()
            if c and c > max_count:
                max_count = c
        if max_count > 0:
            verdict_data["downloaded"] = max_count

    # Year counts (grouped by year and verdict)
    year_counts = db.query(job_model.JobResult.year, job_model.JobResult.verdict, func.count(job_model.JobResult.id)).filter(job_model.JobResult.job_id == job_id).group_by(job_model.JobResult.year, job_model.JobResult.verdict).all()
    
    # Process year data for frontend
    year_data_map = {}
    for year, verdict, count in year_counts:
        if not year: continue 
        if year not in year_data_map:
            year_data_map[year] = {"year": year, "support": 0, "reject": 0, "neutral": 0}
        year_data_map[year][verdict] = count
    
    year_data = sorted(year_data_map.values(), key=lambda x: x['year'])

    if year_data:
        start_idx = 0
        for i, d in enumerate(year_data):
            if d['support'] > 0 or d['reject'] > 0:
                start_idx = i
                break
        
        end_idx = len(year_data)
        for i in range(len(year_data) - 1, -1, -1):
            d = year_data[i]
            if d['support'] > 0 or d['reject'] > 0:
                end_idx = i + 1
                break
        
        has_significant = any(d['support'] > 0 or d['reject'] > 0 for d in year_data)
        if has_significant:
            year_data = year_data[start_idx:end_idx]

    return {
        "verdict_counts": verdict_data,
        "year_data": year_data
    }

@router.get("/{job_id}/summary_image")
def get_job_summary_image(job_id: int, current_user: user_model.User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.query(job_model.Job).filter(job_model.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if not job.summary_image:
        raise HTTPException(status_code=404, detail="Summary image not found")
    
    return Response(content=job.summary_image, media_type="image/png")

@router.get("/{job_id}/download_csv")
def download_job_csv(job_id: int, token: str, db: Session = Depends(get_db)):
    from jose import JWTError, jwt
    from fastapi import status
    from ..core import config
    
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No token provided")
    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        email: str = payload.get("sub")
        if not email:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email missing in token")
    except JWTError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"JWTError: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Error: {str(e)}")
        
    current_user = db.query(user_model.User).filter(user_model.User.email == email).first()
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"User {email} not found")

    job = db.query(job_model.Job).filter(job_model.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Fallback to the binary blob if it exists (legacy jobs)
    has_results = db.query(job_model.JobResult).filter(job_model.JobResult.job_id == job_id).first()
    if not has_results:
        if not job.result_csv:
            raise HTTPException(status_code=404, detail="Results CSV not found")
        return Response(
            content=job.result_csv, 
            media_type='text/csv',
            headers={"Content-Disposition": f"attachment; filename=job_{job_id}_results.csv"}
        )

    def iter_csv():
        from ..db.session import SessionLocal
        local_db = SessionLocal()
        try:
            output = StringIO()
            writer = csv.writer(output)
            writer.writerow(["pmid", "title", "year", "abstract", "verdict", "confidence", "rationale"])
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)
            
            chunk_size = 5000
            offset = 0
            while True:
                results = local_db.query(job_model.JobResult).filter(job_model.JobResult.job_id == job_id).order_by(job_model.JobResult.id).limit(chunk_size).offset(offset).all()
                if not results:
                    break
                for r in results:
                    writer.writerow([r.pmid, r.title, r.year, r.abstract, r.verdict, r.confidence, r.rationale])
                yield output.getvalue()
                output.seek(0)
                output.truncate(0)
                offset += chunk_size
        finally:
            local_db.close()
            
    return StreamingResponse(
        iter_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=job_{job_id}_results.csv"}
    )
