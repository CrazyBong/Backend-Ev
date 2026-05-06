# Backend-Ev

FastAPI backend for the Kairo EV charging app.

## Current Status

The backend is already integrated with the React Native frontend for the main implemented flows:

- OTP auth, token refresh, current-user bootstrap, profile update, logout
- nearby stations and station detail
- slot listing
- bookings create, list, cancel
- payment verification and Razorpay webhook reconciliation
- notifications
- route planning
- demand/pricing reads
- station reviews read path

## What Still Needs To Be Built

The biggest backend gap right now is:

- real station inventory data in the database

The remaining shared end-to-end gaps are:

- discovery and route planning still need live GPS as the real origin
- frontend still needs real WebSocket slot sync
- frontend still needs the final live payment SDK flow

Optional future backend expansion:

- wallet and balance endpoints
- profile summary endpoints
- station import/admin tooling
- richer operator/network integrations

## Local Dev

### Prerequisites

- Python 3.12+
- PostgreSQL with PostGIS
- Redis

### Setup

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in the required values.

### Run Migrations

```powershell
alembic upgrade head
```

### Start the API

```powershell
uvicorn app.main:app --reload
```

API base:

- `http://127.0.0.1:8000`
- Swagger: `http://127.0.0.1:8000/docs`

## Docs

- Endpoint map: [Docs/endpoints.md](C:/Users/Lenovo/Backend-Ev/Docs/endpoints.md)
- API spec: [Docs/API_SPEC.md](C:/Users/Lenovo/Backend-Ev/Docs/API_SPEC.md)

## Notes For Handoff

If someone is taking over deployment or final product completion, the current priority order should be:

1. Seed or import real station inventory data.
2. Switch frontend discovery and route origin to live GPS.
3. Wire real frontend WebSocket slot sync.
4. Replace the remaining simulated mobile checkout path with the final payment SDK flow.
