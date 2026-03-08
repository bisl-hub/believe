import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.db import Base
from app.models import Project, ProjectUser, User, Job, DatasetConfig, AnalysisConfig, ModelConfig

SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://user:password@hypothesis-db:5432/hypothesis_db"
)

print(f"Connecting to {SQLALCHEMY_DATABASE_URL}...")
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def migrate():
    print("1. Creating new tables (projects, project_users)...")
    # Base.metadata.create_all only creates non-existing tables.
    Base.metadata.create_all(engine)
    
    with engine.connect() as conn:
        print("2. Adding project_id columns to existing tables...")
        tables = ["jobs", "dataset_configs", "analysis_configs", "model_configs"]
        for table in tables:
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS project_id INTEGER REFERENCES projects(id);"))
                conn.commit()
                print(f" -> Added project_id to {table}")
            except Exception as e:
                conn.rollback()
                print(f" -> Error or already exists on {table}: {e}")

    print("3. Migrating existing data into 'Archive' project...")
    db = SessionLocal()
    
    # Check if there's any user
    first_user = db.query(User).order_by(User.id.asc()).first()
    if not first_user:
        print("No users found. No data migration needed.")
        db.close()
        return

    # Check or create 'Archive' project
    archive_project = db.query(Project).filter(Project.name == "Archive").first()
    if not archive_project:
        archive_project = Project(
            name="Archive",
            description="Auto-migrated archive for all historical jobs and configs.",
            owner_id=first_user.id
        )
        db.add(archive_project)
        db.commit()
        db.refresh(archive_project)
        print(f" -> Created 'Archive' Project (ID: {archive_project.id})")
    
    # Link ALL existing users to the Archive project
    users = db.query(User).all()
    for u in users:
        link_exists = db.query(ProjectUser).filter_by(project_id=archive_project.id, user_id=u.id).first()
        if not link_exists:
            new_link = ProjectUser(project_id=archive_project.id, user_id=u.id)
            db.add(new_link)
    db.commit()
    print(f" -> Linked {len(users)} users to the Archive project.")

    # Assign all orphaned jobs to Archive
    orphaned_jobs = db.query(Job).filter(Job.project_id == None).all()
    for j in orphaned_jobs:
        j.project_id = archive_project.id
    
    orphaned_datasets = db.query(DatasetConfig).filter(DatasetConfig.project_id == None).all()
    for d in orphaned_datasets:
        d.project_id = archive_project.id
        
    orphaned_analyses = db.query(AnalysisConfig).filter(AnalysisConfig.project_id == None).all()
    for a in orphaned_analyses:
        a.project_id = archive_project.id
        
    orphaned_models = db.query(ModelConfig).filter(ModelConfig.project_id == None).all()
    for m in orphaned_models:
        m.project_id = archive_project.id

    db.commit()
    print(f" -> Ported {len(orphaned_jobs)} jobs, {len(orphaned_datasets)} datasets, {len(orphaned_analyses)} analyses, {len(orphaned_models)} models to Archive.")
    db.close()
    print("Migration Strategy Complete!")

if __name__ == "__main__":
    migrate()
