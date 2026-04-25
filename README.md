# EVChargeFinder — FastAPI Backend

Premium backend service for EV Station Discovery & Slot Booking.

## 🚀 Tech Stack
- **Framework**: FastAPI (Python 3.12)
- **Database**: PostgreSQL with PostGIS (via Supabase)
- **ORM**: SQLAlchemy (Async)
- **Migrations**: Alembic
- **Caching & Locks**: Redis (Sliding Window & Distributed Locks)
- **Maps API**: Google Maps (Distance & Routing)
- **Payments**: Razorpay Integrated
- **Security**: RS256 JWT, FAANG-level IDOR mitigation, Atomic Concurrency
- **Observability**: Request-ID Traceability (X-Request-ID)

## 🛠️ Setup Instructions

### 1. Prerequisites
- Python 3.12+
- PostgreSQL with PostGIS extension
- Redis server

### 2. Installation
```powershell
# Create virtual environment
python -m venv venv

# Activate venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt # or install via pyproject.toml as done in Phase 1
```

### 3. Configuration
Copy `.env.example` to `.env` and fill in your credentials:
```powershell
cp .env.example .env
```

### 4. Database Migrations
```powershell
# Run initial migration
alembic upgrade head
```

### 5. Running the API
```powershell
uvicorn app.main:app --reload
```
The API will be available at `http://localhost:8000`.
Swagger documentation: `http://localhost:8000/docs`.

## 📂 Project Structure
- `app/`: Main application logic
  - `routers/`: API endpoints
  - `models/`: Database models
  - `schemas/`: Pydantic schemas
  - `services/`: Business logic
  - `db/`: Database configuration
- `alembic/`: Database migration scripts
- `tests/`: Multi-phase integration suite (49+ scenarios)
- `scripts/`: Production-ready seeding and cleanup utilities

## 🛡️ Security & Reliability Baseline
This backend has undergone a critical FAANG-level architectural hardening:
- **Zero-Trust Admin**: Granular station-level authorization via `station_managers` table.
- **Atomic Operations**: `INSERT ... ON CONFLICT` for user identity management to prevent race conditions.
- **ACID Integrity**: Explicit transaction boundaries across all mutation services (Auth, Bookings, Payments).
- **Concurrency Control**: Dual-layer locking (Redis Distributed Locks + Postgres `FOR UPDATE`) for booking safety.
- **Traceability**: `X-Request-ID` propagation from middleware to logs for distributed debugging.

## 📜 Roadmap
- [x] Phase 1: Project Scaffold & Database Foundation
- [x] Phase 2: Authentication System (Masked PII)
- [x] Phase 3: Station & Slot API (PostGIS Spatial Queries)
- [x] Phase 4: Booking Engine (Redis & DB Dual-Locks)
- [x] Phase 5: Payment Integration (Razorpay Webhooks)
- [x] Phase 6: Real-Time Layer (In-App Notifications)
- [x] Phase 7: Notifications & Route Planner (Google Maps)
- [x] Phase 8: Admin API & Production Hardening
