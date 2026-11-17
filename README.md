# Jobs API

A FastAPI + Postgres jobs board API with Stripe payments for featured listings.

**Live:** https://jobs-api-no94.onrender.com/docs

## Features
- CRUD endpoints for job listings, with city and sponsorship filters
- PostgreSQL database hosted on Neon, using parameterised SQL to block injection
- Stripe Checkout (test mode) to pay £5 to feature a listing
- Signature-verified Stripe webhook that is idempotent, so duplicate events never double-process
- Reconciliation endpoint that uses Stripe as the source of truth to recover missed webhooks
- Admin routes protected with a header token and constant-time comparison

## Tech stack
Python, FastAPI, PostgreSQL (Neon), psycopg, Stripe, Render

## Endpoints
| Method | Path | Description |
|---|---|---|
| GET | /jobs | List jobs (filters: city, sponsorship) |
| POST | /jobs | Create a job |
| GET | /jobs/{job_id} | Get one job |
| DELETE | /jobs/{job_id} | Delete a job |
| POST | /jobs/{job_id}/feature | Start a Stripe Checkout to feature a job |
| POST | /webhooks/stripe | Stripe webhook receiver |
| POST | /admin/reconcile | Sync missed payments from Stripe (needs X-Admin-Token) |

## Run locally
1. Clone the repo and create a virtual environment.
2. Install dependencies: `pip install -r requirements.txt`
3. Create a `.env` file with:
   ```
   DATABASE_URL=your-neon-connection-string
   STRIPE_SECRET_KEY=sk_test_...
   STRIPE_WEBHOOK_SECRET=whsec_...
   ADMIN_TOKEN=a-long-random-string
   ```
4. Start the server: `uvicorn main:app --reload`
5. Open http://127.0.0.1:8000/docs

## How payments stay correct
1. **Checkout:** Stripe hosts the card page, so card data never touches this server.
2. **Webhook:** each event's signature is verified, and a UNIQUE constraint on the Stripe session id makes repeat deliveries harmless.
3. **Reconciliation:** completed sessions are pulled from Stripe and any missing payments are added safely.