from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from .config import settings
from .db import Job, SessionLocal, init_db
from .schemas import JobCreate, JobRead
from .tasks import run_pipeline


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="AI Reels Factory", version="1.0.0", lifespan=lifespan)
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def frontend():
    return FileResponse(STATIC_DIR / "index.html")


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


@app.get("/jobs/{job_id}/video", response_class=FileResponse)
def download_video(job_id: str):
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if not job:
            raise HTTPException(404, "job not found")
        if job.status != "completed":
            raise HTTPException(409, "video is not ready")

        render_artifact = (job.artifacts or {}).get("render")
        if not render_artifact:
            raise HTTPException(404, "render artifact not found")

    job_root = (settings.work_dir / job_id).resolve()
    video_path = (job_root / render_artifact).resolve()
    if not video_path.is_relative_to(job_root) or not video_path.is_file():
        raise HTTPException(404, "video file not found")

    return FileResponse(
        video_path,
        media_type="video/mp4",
        filename=f"reels-{job_id}.mp4",
        headers={"Cache-Control": "private, max-age=3600"},
    )


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
