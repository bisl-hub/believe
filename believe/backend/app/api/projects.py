from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ..db.session import get_db
from ..models.project import Project, ProjectUser
from ..models.user import User
from ..schemas.project import ProjectCreate, ProjectResponse, ProjectInvite, ProjectUpdate
from ..schemas.user import UserResponse
from .users import get_current_user

router = APIRouter()

@router.post("", response_model=ProjectResponse)
def create_project(project: ProjectCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    new_project = Project(
        name=project.name,
        description=project.description,
        owner_id=current_user.id
    )
    db.add(new_project)
    db.commit()
    db.refresh(new_project)
    
    # Auto-add the creator as a member
    link = ProjectUser(project_id=new_project.id, user_id=current_user.id)
    db.add(link)
    db.commit()
    
    return new_project

@router.get("", response_model=List[ProjectResponse])
def get_projects(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Returns all projects the user is a member of
    projects = db.query(Project).join(ProjectUser).filter(ProjectUser.user_id == current_user.id).all()
    # Ensure they are sorted somehow to remain consistent
    return sorted(projects, key=lambda x: x.id)

@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(project_id: int, updates: ProjectUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    is_member = db.query(ProjectUser).filter(ProjectUser.project_id == project_id, ProjectUser.user_id == current_user.id).first()
    if not is_member:
        raise HTTPException(status_code=403, detail="You must be a member of the project to modify it")

    if updates.name is not None:
        project.name = updates.name
    if updates.description is not None:
        project.description = updates.description
        
    db.commit()
    db.refresh(project)
    return project

@router.delete("/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the owner can delete the project")
    
    db.delete(project)
    db.commit()
    return {"status": "success"}

@router.get("/{project_id}/members", response_model=List[UserResponse])
def get_project_members(project_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    is_member = db.query(ProjectUser).filter(ProjectUser.project_id == project_id, ProjectUser.user_id == current_user.id).first()
    if not is_member:
        raise HTTPException(status_code=403, detail="You must be a member of the project to view its members")

    members = db.query(User).join(ProjectUser).filter(ProjectUser.project_id == project_id).all()
    return members

@router.post("/{project_id}/invite")
def invite_user(project_id: int, invite: ProjectInvite, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Verify current user is a member
    is_member = db.query(ProjectUser).filter(ProjectUser.project_id == project_id, ProjectUser.user_id == current_user.id).first()
    if not is_member:
        raise HTTPException(status_code=403, detail="You must be a member of the project to invite others")
        
    invited_user = db.query(User).filter(User.email == invite.email).first()
    if not invited_user:
        raise HTTPException(status_code=404, detail=f"User with email {invite.email} not found")
    
    existing_link = db.query(ProjectUser).filter(ProjectUser.project_id == project_id, ProjectUser.user_id == invited_user.id).first()
    if existing_link:
        raise HTTPException(status_code=400, detail="User is already a member of this project")
        
    link = ProjectUser(project_id=project_id, user_id=invited_user.id)
    db.add(link)
    db.commit()
    
    return {"status": "success", "message": f"Invited {invited_user.email} successfully"}
