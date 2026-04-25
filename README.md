# EVChargeFinder — FastAPI Backend

Premium backend service for EV Station Discovery & Slot Booking.

## 🚀 Tech Stack
- **Framework**: FastAPI (Python 3.12)
- **Database**: PostgreSQL with PostGIS (via Supabase)
- **ORM**: SQLAlchemy (Async)
- **Migrations**: Alembic
- **Caching**: Redis
- **Payments**: Razorpay
- **Validation**: Pydantic v2

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
- `tests/`: Automated tests
- `scripts/`: Seed data and utilities

## 📜 Roadmap
- [x] Phase 1: Project Scaffold & Database Foundation
- [ ] Phase 2: Authentication System
- [ ] Phase 3: Station & Slot API
- [ ] Phase 4: Booking Engine
- [ ] Phase 5: Payment Integration
- [ ] Phase 6: Real-Time Layer
- [ ] Phase 7: Notifications & Route Planner
- [ ] Phase 8: Admin API & Hardening
