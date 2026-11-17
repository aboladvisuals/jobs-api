import os
import secrets
import psycopg
import stripe
from psycopg.rows import dict_row
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Header
from pydantic import BaseModel

load_dotenv()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
if not stripe.api_key:
    raise RuntimeError("STRIPE_SECRET_KEY is not set")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
if not WEBHOOK_SECRET:
    raise RuntimeError("STRIPE_WEBHOOK_SECRET is not set")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")
if not ADMIN_TOKEN:
    raise RuntimeError("ADMIN_TOKEN is not set")

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
    sql = "SELECT id, title, city, sponsorship, featured FROM jobs WHERE 1=1"
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

@app.post("/jobs/{job_id}/feature")
def feature_job(job_id: int):
    with get_conn() as conn:
        job = conn.execute(
            "SELECT id, title FROM jobs WHERE id = %s",
(job_id,)
        ).fetchone()
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        # Create a Stripe Checkout Session for the feature payment
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[
                {
                    "price_data": {
                        "currency": "gbp",
                        "unit_amount": 500,
                        "product_data": {
                            "name": f"Featured listing: {job['title']}",
                        },
                    },
                    "quantity": 1,
                }
            ],
            metadata={"job_id": str(job_id)},
            success_url="https://jobs-api-no94.onrender.com/docs?paid=yes",
            cancel_url="https://jobs-api-no94.onrender.com/docs?paid=no",
            )
        return {"checkout_url": session.url}

@app.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature")
    try:
        event = stripe.Webhook.construct_event(
            payload, sig, WEBHOOK_SECRET
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid signature")
    

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        job_id = int(session["metadata"]["job_id"])
        with get_conn() as conn:
            row = conn.execute(
                "INSERT INTO payments (stripe_session_id, job_id, amount, currency)"
                " VALUES (%s, %s, %s, %s) "
                "ON CONFLICT(stripe_session_id) DO NOTHING RETURNING id",
                (session["id"], job_id, session["amount_total"], session["currency"]),
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE jobs SET featured = TRUE WHERE id = %s",
                    (job_id,))
                return {"received": True}


@app.post("/admin/reconcile")
def reconcile(x_admin_token: str | None = Header(None)):
    if not x_admin_token or not secrets.compare_digest(x_admin_token, ADMIN_TOKEN):
        raise HTTPException(status_code=401, detail="Unauthorized")
    fixed = []
    sessions = stripe.checkout.Session.list(limit=100, status="complete")
    with get_conn() as conn:
        for s in sessions.auto_paging_iter():
            if s.payment_status != "paid" or "job_id" not in (s.metadata or {}):
                continue
            job_id = int(s.metadata["job_id"])
            row = conn.execute(
                "INSERT INTO payments (stripe_session_id, job_id, amount, currency)"
                " VALUES (%s, %s, %s, %s) "
                "ON CONFLICT(stripe_session_id) DO NOTHING RETURNING id",
                (s.id, job_id, s.amount_total, s.currency),
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE jobs SET featured = TRUE WHERE id = %s",
                    (job_id,))
                fixed.append(s.id)
                return {"missing_payments_fixed": len(fixed), "sessions": fixed}