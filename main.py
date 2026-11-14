from fastapi import FastAPI
import json 
from pathlib import Path

from fastapi import FastAPI, HTTPException

DATA_FILE = Path("jobs.json")

def load_jobs():
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text())
    return [
        {"id": 1, "title": "data analyst", "city": "Hull", "sponsorship": True},
            {"id": 2, "title": "python developer", "city": "London", "sponsorship": False},
            {"id": 3, "title": "SOC analyst", "city": "Birmingham", "sponsorship": True},
    ]
def save_jobs(data):
    DATA_FILE.write_text(json.dumps(data, indent=2))
app = FastAPI()

from pydantic import BaseModel

class JobIn(BaseModel):
    title: str
    city: str
    sponsorship: bool

jobs= load_jobs()

@app.get("/jobs")
def get_jobs(city: str | None = None, sponsorship: bool |None = None):
    filtered_jobs = jobs
    if city is not None:
        filtered_jobs = [job for job in filtered_jobs if job ["city"].lower()==city.lower()]
    if sponsorship is not None:
        filtered_jobs = [job for job in filtered_jobs if job ["sponsorship"] == sponsorship]
    return filtered_jobs

@app.post("/jobs")
def create_job(job: JobIn):
    new_job = {"id": len(jobs) + 1, **job.model_dump()}
    jobs.append(new_job)
    save_jobs(jobs)
    return new_job

@app.get("/jobs/{job_id}")
def get_job(job_id: int):
    job = next((job for job in jobs if job["id"] == job_id), None)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@app.delete("/jobs/{job_id}")
def delete_job(job_id: int):
    global jobs
    job = next((job for job in jobs if job["id"] == job_id), None)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    jobs = [job for job in jobs if job["id"] != job_id]
    save_jobs(jobs)
    return {"message": "Job deleted successfully"}
        