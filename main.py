import os
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set.")

def get_conn():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)

app = FastAPI()

class JobIn(BaseModel):
    title: str
    city: str
    sponsorship: bool

@app.get("/jobs")
def list_jobs(city: str | None = None, sponsorship: bool | None = None):
    sql = "SELECT id, title, city, sponsorship FROM jobs WHERE 1=1"
    params = []
    if city:
        sql += " AND LOWER(city) = LOWER(%s)"
        params.append(city)
    if sponsorship is not None:
        sql += " AND sponsorship = %s"
        params.append(sponsorship)
    sql += " ORDER BY id"
    with get_conn() as conn:
        return conn.execute(sql, params).fetchall()

@app.post("/jobs", status_code=201)
def create_job(job: JobIn):
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO jobs (title, city, sponsorship) VALUES (%s, %s, %s) "
            "RETURNING id, title, city, sponsorship",
            (job.title, job.city, job.sponsorship),
        ).fetchone()
    return row

@app.get("/jobs/{job_id}")
def get_job(job_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, title, city, sponsorship FROM jobs WHERE id = %s",
            (job_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return row

@app.delete("/jobs/{job_id}")
def delete_job(job_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "DELETE FROM jobs WHERE id = %s RETURNING id",
            (job_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"message": "Job deleted successfully"}
