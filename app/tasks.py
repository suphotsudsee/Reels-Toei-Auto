import traceback
from pathlib import Path
from uuid import uuid4
from .celery_app import celery
from .config import settings
from .db import Job, SessionLocal, init_db
from .pipeline import STAGES


@celery.task(name="app.tasks.run_pipeline", bind=True, autoretry_for=(), max_retries=0)
def run_pipeline(self, job_id: str):
    init_db()
    root = settings.work_dir / job_id
    root.mkdir(parents=True, exist_ok=True)
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if not job:
            raise ValueError(f"unknown job {job_id}")
        job.status = "running"
        job.error = None
        db.commit()
        try:
            artifacts = dict(job.artifacts or {})
            for name, stage in STAGES:
                job.current_stage = name
                db.commit()
                output = stage(job, root)
                artifacts[name] = str(Path(output).relative_to(root))
                job.artifacts = dict(artifacts)
                db.commit()
            job.status = "completed"
            job.current_stage = None
            db.commit()
            return {"job_id": job.id, "status": job.status}
        except Exception as exc:
            job.status = "failed"
            job.error = f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=3)}"[:5000]
            db.commit()
            raise


@celery.task(name="app.tasks.create_scheduled_job")
def create_scheduled_job():
    init_db()
    job = Job(id=str(uuid4()), topic=settings.default_topic, language=settings.default_language, target_seconds=settings.default_target_seconds)
    with SessionLocal() as db:
        db.add(job)
        db.commit()
    run_pipeline.delay(job.id)
    return job.id

