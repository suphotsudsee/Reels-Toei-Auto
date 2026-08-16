from contextlib import asynccontextmanager
from uuid import uuid4
from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from .db import Job, SessionLocal, init_db
from .schemas import JobCreate, JobRead
from .tasks import run_pipeline


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="AI Reels Factory", version="1.0.0", lifespan=lifespan)


@app.get("/health")
def health():
    with SessionLocal() as db:
        db.execute(text("select 1"))
    return {"status": "ok"}


@app.post("/jobs", response_model=JobRead, status_code=202)
def create_job(payload: JobCreate):
    job = Job(id=str(uuid4()), **payload.model_dump())
    with SessionLocal() as db:
        db.add(job)
        db.commit()
        db.refresh(job)
    run_pipeline.delay(job.id)
    return job


@app.get("/jobs/{job_id}", response_model=JobRead)
def get_job(job_id: str):
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if not job:
            raise HTTPException(404, "job not found")
        return job


@app.post("/jobs/{job_id}/retry", response_model=JobRead, status_code=202)
def retry_job(job_id: str):
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if not job:
            raise HTTPException(404, "job not found")
        job.status, job.error = "queued", None
        db.commit()
        db.refresh(job)
    run_pipeline.delay(job.id)
    return job

