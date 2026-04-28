from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .db import engine, Base
from .api import auth, users, projects, jobs, configs, api_keys
from .api import v1 as v1_router
from .models import api_key  # ensure table is registered before create_all

# DB Init
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Hypothesis Validation Service")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    """
    On startup, initialize QueueManager.
    """
    from .services.queue_manager import queue_manager
    queue_manager.start()

@app.on_event("shutdown")
def shutdown_event():
    from .services.queue_manager import queue_manager
    queue_manager.stop()

app.include_router(auth.router, prefix="/api", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(api_keys.router, prefix="/api/projects", tags=["api-keys"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(configs.router, prefix="/api/configs", tags=["configs"])
app.include_router(v1_router.router, prefix="/api/v1", tags=["v1 — Public API"])
