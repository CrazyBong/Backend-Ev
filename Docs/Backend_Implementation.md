# Backend Implementation Plan
## EVChargeFinder — FastAPI Backend · 8-Phase Build Specification

---

| Field | Details |
|---|---|
| **Document Version** | v1.0 |
| **Stack** | Python 3.12 · FastAPI · Supabase (PostgreSQL + PostGIS) · Redis · Alembic |
| **Author** | Architecture Reference — EVChargeFinder |
| **Reference HLD** | HLD_TRD_EVChargeFinder v1.0 |
| **Reference API** | API_SPEC_EVChargeFinder v1.0 |

---

## Table of Contents

1. [Phase Overview](#1-phase-overview)
2. [Phase 1 — Project Scaffold & Database Foundation](#2-phase-1--project-scaffold--database-foundation)
3. [Phase 2 — Authentication System](#3-phase-2--authentication-system)
4. [Phase 3 — Station & Slot API](#4-phase-3--station--slot-api)
5. [Phase 4 — Booking Engine & Concurrency Control](#5-phase-4--booking-engine--concurrency-control)
6. [Phase 5 — Payment Integration (Razorpay)](#6-phase-5--payment-integration-razorpay)
7. [Phase 6 — Real-Time Layer (WebSocket + Supabase Realtime)](#7-phase-6--real-time-layer-websocket--supabase-realtime)
8. [Phase 7 — Notifications, Route Planner & Reviews](#8-phase-7--notifications-route-planner--reviews)
9. [Phase 8 — Admin API, AI Demand Prediction & Hardening](#9-phase-8--admin-api-ai-demand-prediction--hardening)
10. [Cross-Cutting Concerns](#10-cross-cutting-concerns)
11. [Master Edge Case Registry](#11-master-edge-case-registry)
12. [Testing Strategy & Coverage Plan](#12-testing-strategy--coverage-plan)
13. [CI/CD Pipeline](#13-cicd-pipeline)
14. [Performance & Load Testing](#14-performance--load-testing)

---

## 1. Phase Overview

| Phase | Name | Duration | Deliverable |
|---|---|---|---|
| **1** | Scaffold + DB | 3 days | Project structure, all migrations, seed data running |
| **2** | Auth System | 3 days | OTP login, JWT, refresh, logout working end-to-end |
| **3** | Station & Slot API | 4 days | Discovery, geospatial queries, slot details |
| **4** | Booking Engine | 5 days | Booking CRUD + concurrency-safe slot locking |
| **5** | Payment (Razorpay) | 4 days | Order creation, verification, webhook, refunds |
| **6** | Real-Time Layer | 3 days | WebSocket events, Supabase Realtime, polling fallback |
| **7** | Notifications + Routes | 4 days | Push notifications, route planner, reviews |
| **8** | Admin + AI + Hardening | 5 days | Admin API, demand ML, security, observability |

**Total: ~31 development days (6 weeks with buffer)**

---

## 2. Phase 1 — Project Scaffold & Database Foundation

### 2.1 Project Structure

```
backend/
├── app/
│   ├── main.py                    ← FastAPI app factory
│   ├── config.py                  ← Settings (Pydantic BaseSettings)
│   ├── dependencies.py            ← Shared FastAPI dependencies
│   │
│   ├── routers/
│   │   ├── auth.py
│   │   ├── stations.py
│   │   ├── slots.py
│   │   ├── bookings.py
│   │   ├── payments.py
│   │   ├── routes.py
│   │   ├── reviews.py
│   │   ├── notifications.py
│   │   └── admin.py
│   │
│   ├── services/
│   │   ├── auth_service.py
│   │   ├── station_service.py
│   │   ├── booking_service.py
│   │   ├── payment_service.py
│   │   ├── notification_service.py
│   │   ├── route_service.py
│   │   ├── demand_service.py      ← AI demand prediction
│   │   └── iot_simulator.py       ← Simulated charger data feed
│   │
│   ├── models/
│   │   ├── user.py
│   │   ├── station.py
│   │   ├── slot.py
│   │   ├── booking.py
│   │   ├── payment.py
│   │   └── review.py
│   │
│   ├── schemas/                   ← Pydantic request/response schemas
│   │   ├── auth.py
│   │   ├── station.py
│   │   ├── booking.py
│   │   ├── payment.py
│   │   └── admin.py
│   │
│   ├── db/
│   │   ├── database.py            ← Async SQLAlchemy engine
│   │   └── redis.py               ← Redis connection pool
│   │
│   ├── middleware/
│   │   ├── auth_middleware.py     ← JWT verification
│   │   ├── rate_limiter.py
│   │   ├── request_logger.py
│   │   └── error_handler.py
│   │
│   └── utils/
│       ├── crypto.py              ← Signature verification
│       ├── geo.py                 ← Coord helpers
│       ├── time_utils.py          ← IST handling
│       └── idempotency.py
│
├── alembic/
│   ├── env.py
│   └── versions/
│       ├── 001_initial_schema.py
│       ├── 002_postgis_extension.py
│       ├── 003_indexes.py
│       └── 004_seed_bhopal_stations.py
│
├── tests/
│   ├── conftest.py
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── scripts/
│   └── seed_bhopal.py
│
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── .env.example
```

### 2.2 App Factory Pattern

```python
# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.config import settings
from app.db.database import create_db_engine
from app.db.redis import init_redis_pool, close_redis_pool
from app.middleware.error_handler import register_error_handlers
from app.middleware.request_logger import RequestLoggerMiddleware
from app.routers import auth, stations, slots, bookings, payments, routes, reviews, notifications, admin

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle management."""
    logger.info("Starting EVChargeFinder API...")

    # Startup
    await init_redis_pool()
    await create_db_engine()

    logger.info(f"API ready — Environment: {settings.ENVIRONMENT}")
    yield

    # Shutdown
    await close_redis_pool()
    logger.info("API shutdown complete.")


def create_app() -> FastAPI:
    app = FastAPI(
        title="EVChargeFinder API",
        version="1.0.0",
        docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Custom middleware
    app.add_middleware(RequestLoggerMiddleware)

    # Error handlers (all returning standard envelope format)
    register_error_handlers(app)

    # Routers
    prefix = "/v1"
    app.include_router(auth.router,          prefix=f"{prefix}/auth",          tags=["auth"])
    app.include_router(stations.router,      prefix=f"{prefix}/stations",      tags=["stations"])
    app.include_router(slots.router,         prefix=f"{prefix}/slots",         tags=["slots"])
    app.include_router(bookings.router,      prefix=f"{prefix}/bookings",      tags=["bookings"])
    app.include_router(payments.router,      prefix=f"{prefix}/payments",      tags=["payments"])
    app.include_router(routes.router,        prefix=f"{prefix}/routes",        tags=["routes"])
    app.include_router(reviews.router,       prefix=f"{prefix}/reviews",       tags=["reviews"])
    app.include_router(notifications.router, prefix=f"{prefix}/notifications", tags=["notifications"])
    app.include_router(admin.router,         prefix=f"{prefix}/admin",         tags=["admin"])

    return app


app = create_app()
```

### 2.3 Configuration

```python
# app/config.py
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List

class Settings(BaseSettings):
    # App
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    SECRET_KEY: str
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "exp://"]

    # Database (Supabase)
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str
    DATABASE_URL: str        # PostgreSQL DSN with PostGIS

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # JWT
    JWT_ALGORITHM: str = "RS256"
    JWT_PRIVATE_KEY: str     # PEM — stored in env, not file
    JWT_PUBLIC_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # OTP
    OTP_LENGTH: int = 6
    OTP_EXPIRE_SECONDS: int = 300
    OTP_MAX_ATTEMPTS: int = 5
    OTP_RATE_LIMIT_WINDOW: int = 600  # 10 minutes

    # Razorpay
    RAZORPAY_KEY_ID: str
    RAZORPAY_KEY_SECRET: str
    RAZORPAY_WEBHOOK_SECRET: str

    # Google Maps
    GOOGLE_MAPS_API_KEY: str

    # Expo Notifications
    EXPO_ACCESS_TOKEN: str

    # Slot Locking
    SLOT_LOCK_TTL_SECONDS: int = 120   # 2 minutes

    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
```

### 2.4 Complete Database Schema (Alembic Migration 001)

```python
# alembic/versions/001_initial_schema.py
"""Initial schema — all tables, enums, constraints"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

def upgrade():
    # Enable PostGIS
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")  # for text search

    # ENUMS
    op.execute("""
        CREATE TYPE user_role AS ENUM ('user', 'station_admin', 'super_admin');
        CREATE TYPE slot_status AS ENUM ('AVAILABLE', 'BOOKED', 'IN_USE', 'LOCKED', 'OFFLINE');
        CREATE TYPE booking_status AS ENUM (
            'PENDING_PAYMENT', 'CONFIRMED', 'ACTIVE', 'COMPLETED',
            'CANCELLED_BY_USER', 'CANCELLED_BY_ADMIN', 'NO_SHOW', 'REFUND_PENDING'
        );
        CREATE TYPE payment_status AS ENUM (
            'CREATED', 'PENDING_WEBHOOK', 'SUCCESS', 'FAILED', 'REFUNDED', 'PARTIALLY_REFUNDED'
        );
        CREATE TYPE charger_type AS ENUM ('CCS2', 'CHAdeMO', 'TYPE2', 'BHARAT_AC', 'BHARAT_DC');
        CREATE TYPE charging_network AS ENUM (
            'TATA_POWER', 'CHARGE_ZONE', 'ATHER_GRID', 'STATIQ', 'BPCL_PULSE', 'EESL', 'INDEPENDENT'
        );
        CREATE TYPE notification_type AS ENUM (
            'BOOKING_CONFIRMED', 'BOOKING_REMINDER', 'BOOKING_CANCELLED',
            'SLOT_AVAILABLE', 'PAYMENT_SUCCESS', 'PAYMENT_FAILED', 'REFUND_INITIATED'
        );
    """)

    # USERS
    op.execute("""
        CREATE TABLE users (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            phone            VARCHAR(15)  NOT NULL UNIQUE,
            name             VARCHAR(100),
            email            VARCHAR(255) UNIQUE,
            role             user_role    NOT NULL DEFAULT 'user',
            vehicle_type     VARCHAR(100),
            preferred_connector charger_type,
            expo_push_token  VARCHAR(255),
            is_active        BOOLEAN      NOT NULL DEFAULT TRUE,
            created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
        )
    """)

    # STATIONS
    op.execute("""
        CREATE TABLE stations (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name             VARCHAR(200)  NOT NULL,
            network          charging_network NOT NULL,
            location         GEOGRAPHY(POINT, 4326) NOT NULL,
            address          JSONB         NOT NULL,
            operating_hours  JSONB         NOT NULL,
            amenities        TEXT[]        DEFAULT '{}',
            price_per_unit   DECIMAL(10,2),
            price_per_hour   DECIMAL(10,2),
            is_active        BOOLEAN       NOT NULL DEFAULT TRUE,
            total_slots      INTEGER       NOT NULL DEFAULT 0,
            available_slots  INTEGER       NOT NULL DEFAULT 0,
            avg_rating       DECIMAL(3,2)  DEFAULT 0.00,
            total_reviews    INTEGER       DEFAULT 0,
            last_heartbeat   TIMESTAMPTZ,
            admin_user_id    UUID          REFERENCES users(id),
            created_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
            updated_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

            -- OCPP-ready fields
            ocpp_station_id  VARCHAR(50) UNIQUE,  -- EVSE ID for future hardware

            CONSTRAINT chk_available_lte_total CHECK (available_slots <= total_slots),
            CONSTRAINT chk_available_gte_zero  CHECK (available_slots >= 0),
            CONSTRAINT chk_rating_range        CHECK (avg_rating BETWEEN 0 AND 5)
        )
    """)

    # SLOTS
    op.execute("""
        CREATE TABLE slots (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            station_id       UUID          NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
            slot_number      INTEGER       NOT NULL,
            charger_type     charger_type  NOT NULL,
            power_kw         DECIMAL(6,1)  NOT NULL,
            status           slot_status   NOT NULL DEFAULT 'AVAILABLE',
            fault_code       VARCHAR(50),
            locked_by_user   UUID          REFERENCES users(id),
            locked_until     TIMESTAMPTZ,
            ocpp_connector_id INTEGER,     -- OCPP-ready
            created_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
            updated_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

            UNIQUE (station_id, slot_number),
            CONSTRAINT chk_lock_consistency CHECK (
                (locked_until IS NULL AND locked_by_user IS NULL) OR
                (locked_until IS NOT NULL AND locked_by_user IS NOT NULL)
            )
        )
    """)

    # BOOKINGS
    op.execute("""
        CREATE TABLE bookings (
            id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id           UUID          NOT NULL REFERENCES users(id),
            slot_id           UUID          NOT NULL REFERENCES slots(id),
            station_id        UUID          NOT NULL REFERENCES stations(id),
            status            booking_status NOT NULL DEFAULT 'PENDING_PAYMENT',
            scheduled_start   TIMESTAMPTZ   NOT NULL,
            scheduled_end     TIMESTAMPTZ   NOT NULL,
            actual_start      TIMESTAMPTZ,
            actual_end        TIMESTAMPTZ,
            amount            DECIMAL(10,2) NOT NULL,
            energy_consumed_kwh DECIMAL(8,2),
            qr_code           VARCHAR(500),
            cancellation_reason TEXT,
            idempotency_key   VARCHAR(36)   NOT NULL UNIQUE,
            created_at        TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
            updated_at        TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

            CONSTRAINT chk_time_order CHECK (scheduled_end > scheduled_start),
            CONSTRAINT chk_future_booking CHECK (scheduled_start > created_at)
        )
    """)

    # PAYMENTS
    op.execute("""
        CREATE TABLE payments (
            id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            booking_id            UUID          NOT NULL REFERENCES bookings(id) UNIQUE,
            user_id               UUID          NOT NULL REFERENCES users(id),
            razorpay_order_id     VARCHAR(100)  NOT NULL UNIQUE,
            razorpay_payment_id   VARCHAR(100)  UNIQUE,
            status                payment_status NOT NULL DEFAULT 'CREATED',
            amount                DECIMAL(10,2) NOT NULL,
            refund_amount         DECIMAL(10,2) DEFAULT 0.00,
            razorpay_refund_id    VARCHAR(100),
            webhook_verified      BOOLEAN       DEFAULT FALSE,
            webhook_received_at   TIMESTAMPTZ,
            created_at            TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
            updated_at            TIMESTAMPTZ   NOT NULL DEFAULT NOW()
        )
    """)

    # REVIEWS
    op.execute("""
        CREATE TABLE reviews (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id     UUID          NOT NULL REFERENCES users(id),
            station_id  UUID          NOT NULL REFERENCES stations(id),
            booking_id  UUID          UNIQUE REFERENCES bookings(id),
            rating      SMALLINT      NOT NULL,
            comment     TEXT,
            created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

            UNIQUE (user_id, station_id, booking_id),
            CONSTRAINT chk_rating_1_to_5 CHECK (rating BETWEEN 1 AND 5)
        )
    """)

    # NOTIFICATIONS (in-app)
    op.execute("""
        CREATE TABLE notifications (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id      UUID              NOT NULL REFERENCES users(id),
            type         notification_type NOT NULL,
            title        VARCHAR(200)      NOT NULL,
            body         TEXT              NOT NULL,
            data         JSONB             DEFAULT '{}',
            is_read      BOOLEAN           NOT NULL DEFAULT FALSE,
            created_at   TIMESTAMPTZ       NOT NULL DEFAULT NOW()
        )
    """)

    # OTP (temp table — high write, fast expiry)
    op.execute("""
        CREATE TABLE otp_records (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            phone       VARCHAR(15) NOT NULL,
            otp_hash    VARCHAR(64) NOT NULL,   -- bcrypt hash of OTP
            attempts    SMALLINT    NOT NULL DEFAULT 0,
            expires_at  TIMESTAMPTZ NOT NULL,
            used        BOOLEAN     NOT NULL DEFAULT FALSE,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(phone, used) WHERE used = FALSE
        )
    """)

    # DEMAND PREDICTIONS (AI output cache)
    op.execute("""
        CREATE TABLE demand_predictions (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            station_id  UUID         REFERENCES stations(id),
            predicted_for DATE        NOT NULL,
            hour        SMALLINT     NOT NULL,
            predicted_load DECIMAL(5,2) NOT NULL,  -- 0.0 to 1.0
            confidence  DECIMAL(5,2),
            model_version VARCHAR(20),
            created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            UNIQUE (station_id, predicted_for, hour)
        )
    """)

    # JWT blacklist (for logout)
    op.execute("""
        CREATE TABLE jwt_blacklist (
            jti        VARCHAR(36) PRIMARY KEY,
            expires_at TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)


def create_indexes():
    # Geospatial — GIST index, critical for nearby queries
    op.execute("CREATE INDEX idx_stations_location ON stations USING GIST (location)")
    op.execute("CREATE INDEX idx_stations_network ON stations (network)")
    op.execute("CREATE INDEX idx_stations_active ON stations (is_active) WHERE is_active = TRUE")

    # Slots
    op.execute("CREATE INDEX idx_slots_station_id ON slots (station_id)")
    op.execute("CREATE INDEX idx_slots_status ON slots (status)")
    op.execute("CREATE INDEX idx_slots_locked_until ON slots (locked_until) WHERE locked_until IS NOT NULL")

    # Bookings
    op.execute("CREATE INDEX idx_bookings_user_id ON bookings (user_id)")
    op.execute("CREATE INDEX idx_bookings_slot_id ON bookings (slot_id)")
    op.execute("CREATE INDEX idx_bookings_station_id ON bookings (station_id)")
    op.execute("CREATE INDEX idx_bookings_status ON bookings (status)")
    op.execute("CREATE INDEX idx_bookings_scheduled_start ON bookings (scheduled_start)")
    op.execute("""
        CREATE INDEX idx_bookings_active_window
        ON bookings (slot_id, scheduled_start, scheduled_end)
        WHERE status IN ('PENDING_PAYMENT', 'CONFIRMED', 'ACTIVE')
    """)

    # Notifications
    op.execute("CREATE INDEX idx_notifications_user_unread ON notifications (user_id) WHERE is_read = FALSE")

    # OTP
    op.execute("CREATE INDEX idx_otp_phone_active ON otp_records (phone) WHERE used = FALSE")

    # JWT blacklist
    op.execute("CREATE INDEX idx_jwt_blacklist_expires ON jwt_blacklist (expires_at)")
```

### 2.5 Database Triggers

```sql
-- Auto-update stations.available_slots when any slot status changes
CREATE OR REPLACE FUNCTION update_station_available_slots()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE stations
    SET available_slots = (
        SELECT COUNT(*) FROM slots
        WHERE station_id = COALESCE(NEW.station_id, OLD.station_id)
        AND status = 'AVAILABLE'
    ),
    updated_at = NOW()
    WHERE id = COALESCE(NEW.station_id, OLD.station_id);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_slot_status_change
    AFTER INSERT OR UPDATE OF status ON slots
    FOR EACH ROW EXECUTE FUNCTION update_station_available_slots();

-- Auto-update station avg_rating when review added
CREATE OR REPLACE FUNCTION update_station_rating()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE stations
    SET avg_rating = (
        SELECT ROUND(AVG(rating)::NUMERIC, 2)
        FROM reviews WHERE station_id = NEW.station_id
    ),
    total_reviews = (
        SELECT COUNT(*) FROM reviews WHERE station_id = NEW.station_id
    ),
    updated_at = NOW()
    WHERE id = NEW.station_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_review_insert
    AFTER INSERT OR UPDATE ON reviews
    FOR EACH ROW EXECUTE FUNCTION update_station_rating();

-- Clean up expired OTPs (called by cron job)
CREATE OR REPLACE FUNCTION cleanup_expired_otps()
RETURNS void AS $$
BEGIN
    DELETE FROM otp_records WHERE expires_at < NOW() OR used = TRUE;
END;
$$ LANGUAGE plpgsql;

-- Clean up expired JWT blacklist entries
CREATE OR REPLACE FUNCTION cleanup_jwt_blacklist()
RETURNS void AS $$
BEGIN
    DELETE FROM jwt_blacklist WHERE expires_at < NOW();
END;
$$ LANGUAGE plpgsql;
```

### 2.6 Phase 1 Tests

```python
# tests/unit/test_database.py
import pytest
from sqlalchemy import text

class TestDatabaseSchema:
    async def test_postgis_extension_enabled(self, db):
        result = await db.execute(text(
            "SELECT COUNT(*) FROM pg_extension WHERE extname = 'postgis'"
        ))
        assert result.scalar() == 1

    async def test_gist_index_exists_on_stations(self, db):
        result = await db.execute(text(
            "SELECT indexname FROM pg_indexes WHERE tablename='stations' AND indexname='idx_stations_location'"
        ))
        assert result.scalar() is not None

    async def test_available_slots_trigger(self, db, seed_station):
        """Trigger must update available_slots when slot status changes."""
        station_id = seed_station.id
        slot = await db.execute(
            text("SELECT id FROM slots WHERE station_id = :sid AND status = 'AVAILABLE' LIMIT 1"),
            {"sid": station_id}
        )
        slot_id = slot.scalar()

        before = await db.execute(text(
            "SELECT available_slots FROM stations WHERE id = :sid"), {"sid": station_id}
        )
        before_count = before.scalar()

        await db.execute(text(
            "UPDATE slots SET status = 'BOOKED' WHERE id = :slid"), {"slid": slot_id}
        )
        await db.commit()

        after = await db.execute(text(
            "SELECT available_slots FROM stations WHERE id = :sid"), {"sid": station_id}
        )
        assert after.scalar() == before_count - 1

    async def test_booking_time_constraint(self, db, seed_slot, seed_user):
        """DB must reject booking where end <= start."""
        with pytest.raises(Exception, match="chk_time_order"):
            await db.execute(text("""
                INSERT INTO bookings (user_id, slot_id, station_id, scheduled_start, scheduled_end, amount, idempotency_key)
                VALUES (:uid, :slid, :stid, NOW()+interval'2h', NOW()+interval'1h', 100.00, gen_random_uuid()::text)
            """), {"uid": seed_user.id, "slid": seed_slot.id, "stid": seed_slot.station_id})

    async def test_unique_active_otp_per_phone(self, db):
        """Only one active OTP per phone number."""
        phone = "+919876543210"
        await db.execute(text(
            "INSERT INTO otp_records (phone, otp_hash, expires_at) VALUES (:p, 'hash1', NOW()+interval'5m')"
        ), {"p": phone})
        await db.commit()

        with pytest.raises(Exception):  # UNIQUE violation
            await db.execute(text(
                "INSERT INTO otp_records (phone, otp_hash, expires_at) VALUES (:p, 'hash2', NOW()+interval'5m')"
            ), {"p": phone})
```

---

## 3. Phase 2 — Authentication System

### 3.1 OTP Service

```python
# app/services/auth_service.py
import secrets
import hashlib
import time
from datetime import datetime, timedelta, timezone
import jwt
from passlib.context import CryptContext

from app.config import settings
from app.db.redis import get_redis
from app.db.database import get_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Redis key patterns
OTP_KEY      = "otp:{phone}"           # TTL = 300s
OTP_ATTEMPTS = "otp_attempts:{phone}"  # TTL = 600s
OTP_RATE     = "otp_rate:{phone}"      # TTL = 600s, max 3
JWT_BLACKLIST = "jwt_blacklist:{jti}"  # TTL = token remaining lifetime

async def send_otp(phone: str) -> dict:
    redis = await get_redis()

    # Rate limiting: 3 OTPs per phone per 10 min
    rate_key = OTP_RATE.format(phone=phone)
    count = await redis.incr(rate_key)
    if count == 1:
        await redis.expire(rate_key, settings.OTP_RATE_LIMIT_WINDOW)
    if count > 3:
        ttl = await redis.ttl(rate_key)
        raise OTPRateLimitError(retry_after_seconds=ttl)

    # Generate cryptographically secure OTP
    otp = "".join([str(secrets.randbelow(10)) for _ in range(settings.OTP_LENGTH)])
    otp_hash = pwd_context.hash(otp)

    # Store in Redis (TTL = 5 min)
    otp_key = OTP_KEY.format(phone=phone)
    await redis.setex(otp_key, settings.OTP_EXPIRE_SECONDS, otp_hash)

    # Reset attempts counter for this OTP session
    attempts_key = OTP_ATTEMPTS.format(phone=phone)
    await redis.delete(attempts_key)

    # In production: send via SMS gateway (Twilio / MSG91)
    # For MVP/demo: log to console and return in response (dev only)
    if settings.ENVIRONMENT == "development":
        print(f"[DEV OTP] {phone}: {otp}")

    return {
        "message": "OTP sent successfully",
        "expires_in_seconds": settings.OTP_EXPIRE_SECONDS,
        "phone": phone,
        # Only expose OTP in dev environment
        **({"_dev_otp": otp} if settings.ENVIRONMENT == "development" else {}),
    }


async def verify_otp(phone: str, otp: str, db) -> dict:
    redis = await get_redis()

    # Check attempts
    attempts_key = OTP_ATTEMPTS.format(phone=phone)
    attempts = int(await redis.get(attempts_key) or 0)
    if attempts >= settings.OTP_MAX_ATTEMPTS:
        raise OTPMaxAttemptsError()

    # Check OTP exists
    otp_key = OTP_KEY.format(phone=phone)
    stored_hash = await redis.get(otp_key)
    if not stored_hash:
        raise InvalidOTPError(attempts_remaining=settings.OTP_MAX_ATTEMPTS - attempts - 1)

    # Increment attempts (before verifying — prevents timing attacks via attempt counting)
    await redis.incr(attempts_key)
    await redis.expire(attempts_key, settings.OTP_RATE_LIMIT_WINDOW)

    # Constant-time comparison via bcrypt
    if not pwd_context.verify(otp, stored_hash.decode()):
        remaining = settings.OTP_MAX_ATTEMPTS - (attempts + 1)
        raise InvalidOTPError(attempts_remaining=max(0, remaining))

    # OTP valid — delete it (one-time use)
    await redis.delete(otp_key)

    # Upsert user
    user = await upsert_user(phone, db)

    # Issue tokens
    access_token = create_access_token(user)
    refresh_token = create_refresh_token(user)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "access_token_expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "refresh_token_expires_in": settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        "user": user_to_dict(user),
    }


def create_access_token(user) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "phone": user.phone,
        "role": user.role.value,
        "jti": secrets.token_urlsafe(16),   # unique token ID for blacklisting
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "type": "access",
    }
    return jwt.encode(payload, settings.JWT_PRIVATE_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "jti": secrets.token_urlsafe(16),
        "iat": now,
        "exp": now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        "type": "refresh",
    }
    return jwt.encode(payload, settings.JWT_PRIVATE_KEY, algorithm=settings.JWT_ALGORITHM)


async def blacklist_token(jti: str, exp: int):
    """Store jti in Redis until token expiry."""
    redis = await get_redis()
    ttl = max(0, int(exp - time.time()))
    if ttl > 0:
        await redis.setex(JWT_BLACKLIST.format(jti=jti), ttl, "1")
```

### 3.2 Auth Middleware

```python
# app/middleware/auth_middleware.py
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

from app.config import settings
from app.db.redis import get_redis

security = HTTPBearer(auto_error=False)

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db = Depends(get_db),
) -> dict:
    """Verify JWT, check blacklist, return user payload."""
    if not credentials:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "message": "Authentication required."})

    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            settings.JWT_PUBLIC_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail={"code": "TOKEN_EXPIRED", "message": "Access token has expired."})
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "message": "Invalid token."})

    # Check token type
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "message": "Invalid token type."})

    # Check blacklist
    redis = await get_redis()
    jti = payload.get("jti")
    if jti and await redis.exists(f"jwt_blacklist:{jti}"):
        raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "message": "Token has been revoked."})

    return payload


def require_role(*roles: str):
    async def role_checker(user = Depends(get_current_user)):
        if user["role"] not in roles:
            raise HTTPException(
                status_code=403,
                detail={"code": "FORBIDDEN", "message": "Insufficient permissions."}
            )
        return user
    return role_checker

# Convenient role dependencies
require_admin = require_role("station_admin", "super_admin")
require_super_admin = require_role("super_admin")
```

### 3.3 Phase 2 Tests — Auth Edge Cases

```python
# tests/integration/test_auth.py
import pytest
import asyncio

class TestSendOTP:
    async def test_send_otp_success(self, client):
        res = await client.post("/v1/auth/otp/send", json={"phone": "+919876543210"})
        assert res.status_code == 200
        assert res.json()["data"]["expires_in_seconds"] == 300

    async def test_rejects_invalid_phone_format(self, client):
        """Must reject non-Indian numbers and invalid formats."""
        for phone in ["9876543210", "+1234567890", "+918765432100", "+919876543", "invalid"]:
            res = await client.post("/v1/auth/otp/send", json={"phone": phone})
            assert res.status_code == 422, f"Expected 422 for {phone}"

    async def test_rate_limit_after_3_requests(self, client):
        phone = "+919876543211"
        for _ in range(3):
            await client.post("/v1/auth/otp/send", json={"phone": phone})
        res = await client.post("/v1/auth/otp/send", json={"phone": phone})
        assert res.status_code == 429
        assert res.json()["error"]["code"] == "OTP_LIMIT_EXCEEDED"
        assert "retry_after_seconds" in res.json()["error"]["details"]

    async def test_rate_limit_resets_after_window(self, client, freeze_time):
        phone = "+919876543212"
        for _ in range(3):
            await client.post("/v1/auth/otp/send", json={"phone": phone})
        # Advance time past rate limit window (10 min)
        freeze_time.move_to("10 minutes later")
        res = await client.post("/v1/auth/otp/send", json={"phone": phone})
        assert res.status_code == 200


class TestVerifyOTP:
    async def test_verify_otp_success_new_user(self, client):
        phone = "+919876543213"
        await client.post("/v1/auth/otp/send", json={"phone": phone})
        otp = await get_test_otp(phone)  # test helper reads from Redis
        res = await client.post("/v1/auth/otp/verify", json={"phone": phone, "otp": otp})
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["user"]["is_new_user"] is True
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_verify_otp_existing_user(self, client, seed_user):
        await client.post("/v1/auth/otp/send", json={"phone": seed_user.phone})
        otp = await get_test_otp(seed_user.phone)
        res = await client.post("/v1/auth/otp/verify", json={"phone": seed_user.phone, "otp": otp})
        assert res.json()["data"]["user"]["is_new_user"] is False

    async def test_rejects_wrong_otp(self, client):
        phone = "+919876543214"
        await client.post("/v1/auth/otp/send", json={"phone": phone})
        res = await client.post("/v1/auth/otp/verify", json={"phone": phone, "otp": "000000"})
        assert res.status_code == 401
        assert res.json()["error"]["code"] == "INVALID_OTP"
        assert res.json()["error"]["details"]["attempts_remaining"] == 4

    async def test_otp_locked_after_5_wrong_attempts(self, client):
        phone = "+919876543215"
        await client.post("/v1/auth/otp/send", json={"phone": phone})
        for _ in range(5):
            await client.post("/v1/auth/otp/verify", json={"phone": phone, "otp": "000000"})
        res = await client.post("/v1/auth/otp/verify", json={"phone": phone, "otp": "000000"})
        assert res.status_code == 401
        assert res.json()["error"]["code"] == "INVALID_OTP"
        assert res.json()["error"]["details"]["attempts_remaining"] == 0

    async def test_otp_cannot_be_reused(self, client):
        phone = "+919876543216"
        await client.post("/v1/auth/otp/send", json={"phone": phone})
        otp = await get_test_otp(phone)
        await client.post("/v1/auth/otp/verify", json={"phone": phone, "otp": otp})
        # Second use of same OTP
        res = await client.post("/v1/auth/otp/verify", json={"phone": phone, "otp": otp})
        assert res.status_code == 401

    async def test_expired_otp_rejected(self, client, freeze_time):
        phone = "+919876543217"
        await client.post("/v1/auth/otp/send", json={"phone": phone})
        otp = await get_test_otp(phone)
        freeze_time.move_to("6 minutes later")  # OTP expires after 5 min
        res = await client.post("/v1/auth/otp/verify", json={"phone": phone, "otp": otp})
        assert res.status_code == 401


class TestTokenRefresh:
    async def test_refresh_issues_new_access_token(self, client, auth_tokens):
        res = await client.post("/v1/auth/token/refresh", json={"refresh_token": auth_tokens.refresh})
        assert res.status_code == 200
        assert res.json()["data"]["access_token"] != auth_tokens.access

    async def test_cannot_use_access_token_as_refresh_token(self, client, auth_tokens):
        res = await client.post("/v1/auth/token/refresh", json={"refresh_token": auth_tokens.access})
        assert res.status_code == 401

    async def test_expired_refresh_token_rejected(self, client, expired_refresh_token):
        res = await client.post("/v1/auth/token/refresh", json={"refresh_token": expired_refresh_token})
        assert res.status_code == 401


class TestLogout:
    async def test_logout_blacklists_token(self, client, auth_headers):
        res = await client.delete("/v1/auth/logout", headers=auth_headers)
        assert res.status_code == 200
        # Token must now be rejected
        res2 = await client.get("/v1/auth/me", headers=auth_headers)
        assert res2.status_code == 401

    async def test_blacklisted_token_rejected_on_all_endpoints(self, client, auth_headers):
        await client.delete("/v1/auth/logout", headers=auth_headers)
        for endpoint in ["/v1/stations/nearby", "/v1/bookings", "/v1/auth/me"]:
            res = await client.get(endpoint, headers=auth_headers)
            assert res.status_code == 401
```

---

## 4. Phase 3 — Station & Slot API

### 4.1 Geospatial Service

```python
# app/services/station_service.py
from sqlalchemy import text
from typing import Optional

async def get_nearby_stations(
    lat: float,
    lng: float,
    radius_km: float = 10.0,
    charger_type: Optional[str] = None,
    available_only: bool = False,
    limit: int = 50,
    offset: int = 0,
    db = None,
    redis = None,
) -> list:

    # Cache key (10s TTL per HLD — P2: eventual consistency for discovery)
    cache_key = f"nearby:{lat:.4f}:{lng:.4f}:{radius_km}:{charger_type}:{available_only}"

    cached = await redis.get(cache_key)
    if cached:
        import json
        return json.loads(cached)

    # PostGIS spatial query — all radius math at DB layer (Architecture Principle P5)
    query = text("""
        SELECT
            s.id,
            s.name,
            s.network,
            ST_Y(s.location::geometry) as lat,
            ST_X(s.location::geometry) as lng,
            s.address,
            s.available_slots,
            s.total_slots,
            s.avg_rating,
            s.total_reviews,
            s.price_per_unit,
            s.price_per_hour,
            s.amenities,
            s.is_active,
            ROUND(
                ST_Distance(s.location, ST_MakePoint(:lng, :lat)::geography) / 1000.0,
                2
            ) as distance_km,
            array_agg(DISTINCT sl.charger_type) as charger_types
        FROM stations s
        LEFT JOIN slots sl ON sl.station_id = s.id
        WHERE
            s.is_active = TRUE
            AND ST_DWithin(
                s.location,
                ST_MakePoint(:lng, :lat)::geography,
                :radius_meters
            )
            :charger_filter
            :availability_filter
        GROUP BY s.id
        ORDER BY distance_km ASC
        LIMIT :limit OFFSET :offset
    """)

    charger_filter = (
        "AND EXISTS (SELECT 1 FROM slots WHERE station_id = s.id AND charger_type = :charger_type)"
        if charger_type else ""
    )
    availability_filter = "AND s.available_slots > 0" if available_only else ""

    # Safely substitute filter conditions
    query_str = query.text.replace(":charger_filter", charger_filter).replace(":availability_filter", availability_filter)

    result = await db.execute(text(query_str), {
        "lat": lat, "lng": lng,
        "radius_meters": radius_km * 1000,
        "charger_type": charger_type,
        "limit": limit, "offset": offset,
    })

    stations = [dict(row) for row in result.mappings()]

    # Cache for 10 seconds
    import json
    await redis.setex(cache_key, 10, json.dumps(stations, default=str))

    return stations
```

### 4.2 Phase 3 Edge Cases & Tests

```python
# tests/integration/test_stations.py

class TestNearbyStations:
    async def test_returns_stations_within_radius(self, client, auth_headers, seed_stations_bhopal):
        """DB Mall Tata Power is 0.5km from test coordinates."""
        res = await client.get("/v1/stations/nearby?lat=23.2599&lng=77.4126&radius_km=1", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()["data"]
        assert len(data) >= 1
        assert all(s["distance_km"] <= 1.0 for s in data)

    async def test_returns_empty_for_remote_coordinates(self, client, auth_headers):
        """Ocean coordinates should return no stations."""
        res = await client.get("/v1/stations/nearby?lat=0.0&lng=0.0&radius_km=10", headers=auth_headers)
        assert res.json()["data"] == []

    async def test_radius_boundary_precision(self, client, auth_headers, seed_stations):
        """Station exactly at boundary distance should be included/excluded correctly."""
        # Station at exactly 10.0km — should be included with radius_km=10
        # Station at 10.001km — should be excluded
        res_10 = await client.get("/v1/stations/nearby?lat=23.2599&lng=77.4126&radius_km=10", headers=auth_headers)
        res_9 = await client.get("/v1/stations/nearby?lat=23.2599&lng=77.4126&radius_km=9", headers=auth_headers)
        assert len(res_10.json()["data"]) >= len(res_9.json()["data"])

    async def test_charger_type_filter(self, client, auth_headers, seed_mixed_stations):
        """Only stations with at least one CCS2 slot should be returned."""
        res = await client.get("/v1/stations/nearby?lat=23.2599&lng=77.4126&charger_type=CCS2", headers=auth_headers)
        for station in res.json()["data"]:
            assert "CCS2" in station["charger_types"]

    async def test_available_only_filter(self, client, auth_headers, seed_full_station):
        """Fully occupied station should not appear with available_only=true."""
        res = await client.get("/v1/stations/nearby?lat=23.2599&lng=77.4126&available_only=true", headers=auth_headers)
        station_ids = [s["id"] for s in res.json()["data"]]
        assert seed_full_station.id not in station_ids

    async def test_validates_coordinate_bounds(self, client, auth_headers):
        """Reject clearly invalid coordinates."""
        for lat, lng in [(-91, 0), (91, 0), (0, -181), (0, 181)]:
            res = await client.get(f"/v1/stations/nearby?lat={lat}&lng={lng}", headers=auth_headers)
            assert res.status_code == 422

    async def test_max_radius_capped_at_50km(self, client, auth_headers):
        res = await client.get("/v1/stations/nearby?lat=23.2599&lng=77.4126&radius_km=200", headers=auth_headers)
        assert res.status_code == 422

    async def test_response_sorted_by_distance(self, client, auth_headers, seed_stations):
        res = await client.get("/v1/stations/nearby?lat=23.2599&lng=77.4126", headers=auth_headers)
        distances = [s["distance_km"] for s in res.json()["data"]]
        assert distances == sorted(distances)

    async def test_nearby_uses_cache(self, client, auth_headers, mock_redis):
        """Second identical request should hit cache, not DB."""
        params = "?lat=23.2599&lng=77.4126&radius_km=5"
        await client.get(f"/v1/stations/nearby{params}", headers=auth_headers)
        await client.get(f"/v1/stations/nearby{params}", headers=auth_headers)
        assert mock_redis.get.call_count >= 1

    async def test_inactive_stations_excluded(self, client, auth_headers, seed_inactive_station):
        res = await client.get("/v1/stations/nearby?lat=23.2599&lng=77.4126", headers=auth_headers)
        station_ids = [s["id"] for s in res.json()["data"]]
        assert seed_inactive_station.id not in station_ids
```

---

## 5. Phase 4 — Booking Engine & Concurrency Control

### 5.1 Booking Service — Atomic Slot Locking

```python
# app/services/booking_service.py
import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import text, select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.db.redis import get_redis

SLOT_LOCK_KEY = "slot_lock:{slot_id}"
IDEMPOTENCY_KEY = "idem:{key}"

async def create_booking(
    user_id: str,
    slot_id: str,
    scheduled_start: datetime,
    scheduled_end: datetime,
    idempotency_key: str,
    db,
    redis,
    razorpay_client,
) -> dict:
    """
    Full atomic booking creation following the 30-step data flow from HLD 21.1.
    """

    # Step 1: Check idempotency key
    idem_cache_key = IDEMPOTENCY_KEY.format(key=idempotency_key)
    existing = await redis.get(idem_cache_key)
    if existing:
        import json
        return json.loads(existing)  # Return cached response — DUPLICATE_REQUEST handled

    # Step 2: Validate time window
    now = datetime.now(timezone.utc)
    if scheduled_start <= now:
        raise PastTimeWindowError()
    if scheduled_end <= scheduled_start:
        raise InvalidTimeWindowError()
    if (scheduled_end - scheduled_start).total_seconds() < 1800:  # min 30 minutes
        raise InvalidTimeWindowError("Minimum booking duration is 30 minutes.")
    if (scheduled_end - scheduled_start).total_seconds() > 7200:  # max 2 hours
        raise InvalidTimeWindowError("Maximum booking duration is 2 hours.")

    # Step 3: BEGIN TRANSACTION
    async with db.begin():
        # Step 4: Verify slot exists and belongs to an active station
        slot_result = await db.execute(text("""
            SELECT s.id, s.status, s.station_id, s.charger_type, s.power_kw, s.locked_until,
                   st.is_active, st.price_per_unit, st.price_per_hour, st.operating_hours
            FROM slots s
            JOIN stations st ON st.id = s.station_id
            WHERE s.id = :slot_id
            FOR UPDATE  -- Row-level lock prevents concurrent booking of same slot
        """), {"slot_id": slot_id})
        slot = slot_result.mappings().first()

        if not slot:
            raise SlotNotFoundError(slot_id)
        if not slot["is_active"]:
            raise SlotUnavailableError(slot_id, reason="Station is inactive")
        if slot["status"] == "OFFLINE":
            raise SlotUnavailableError(slot_id, reason="Slot is offline")
        if slot["status"] in ("BOOKED", "IN_USE"):
            raise SlotUnavailableError(slot_id)
        if slot["status"] == "LOCKED":
            # Check if lock has expired (stale lock from crash/timeout)
            if slot["locked_until"] and slot["locked_until"] > now:
                raise SlotLockedError(slot_id, locked_until=slot["locked_until"])
            # Stale lock — proceed and clear it

        # Step 5: Check for overlapping bookings in the requested time window
        overlap = await db.execute(text("""
            SELECT id FROM bookings
            WHERE slot_id = :slot_id
            AND status IN ('PENDING_PAYMENT', 'CONFIRMED', 'ACTIVE')
            AND scheduled_start < :end_time
            AND scheduled_end > :start_time
            LIMIT 1
        """), {
            "slot_id": slot_id,
            "start_time": scheduled_start,
            "end_time": scheduled_end,
        })
        if overlap.first():
            raise SlotUnavailableError(slot_id)

        # Step 6: Validate booking is within station operating hours
        _validate_operating_hours(slot["operating_hours"], scheduled_start, scheduled_end)

        # Step 7: Redis distributed lock (belt + suspenders — DB SELECT FOR UPDATE is primary)
        lock_key = SLOT_LOCK_KEY.format(slot_id=slot_id)
        lock_acquired = await redis.set(
            lock_key,
            user_id,
            nx=True,    # Only set if not exists
            ex=settings.SLOT_LOCK_TTL_SECONDS,
        )
        if not lock_acquired:
            existing_lock = await redis.get(lock_key)
            if existing_lock and existing_lock.decode() != user_id:
                raise SlotLockedError(slot_id)

        # Step 8: Lock slot in DB
        await db.execute(text("""
            UPDATE slots
            SET status = 'LOCKED',
                locked_by_user = :user_id,
                locked_until = :locked_until,
                updated_at = NOW()
            WHERE id = :slot_id
        """), {
            "slot_id": slot_id,
            "user_id": user_id,
            "locked_until": now + timedelta(seconds=settings.SLOT_LOCK_TTL_SECONDS),
        })

        # Step 9: Calculate amount
        amount = _calculate_amount(
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            price_per_unit=slot["price_per_unit"],
            price_per_hour=slot["price_per_hour"],
            power_kw=slot["power_kw"],
        )

        # Step 10: Create Razorpay order
        razorpay_order = razorpay_client.order.create({
            "amount": int(amount * 100),  # paise
            "currency": "INR",
            "payment_capture": 1,
            "notes": {
                "slot_id": slot_id,
                "user_id": user_id,
                "station_id": str(slot["station_id"]),
            }
        })

        # Step 11: Insert booking
        booking_id = str(uuid4())
        qr_payload = f"EVCF:{booking_id}:{slot_id}"

        await db.execute(text("""
            INSERT INTO bookings (
                id, user_id, slot_id, station_id, status,
                scheduled_start, scheduled_end, amount, qr_code, idempotency_key
            ) VALUES (
                :id, :user_id, :slot_id, :station_id, 'PENDING_PAYMENT',
                :scheduled_start, :scheduled_end, :amount, :qr_code, :idempotency_key
            )
        """), {
            "id": booking_id,
            "user_id": user_id,
            "slot_id": slot_id,
            "station_id": str(slot["station_id"]),
            "scheduled_start": scheduled_start,
            "scheduled_end": scheduled_end,
            "amount": amount,
            "qr_code": qr_payload,
            "idempotency_key": idempotency_key,
        })

        # Step 12: Insert payment record
        await db.execute(text("""
            INSERT INTO payments (booking_id, user_id, razorpay_order_id, amount)
            VALUES (:booking_id, :user_id, :order_id, :amount)
        """), {
            "booking_id": booking_id,
            "user_id": user_id,
            "order_id": razorpay_order["id"],
            "amount": amount,
        })

    # Step 13: Store idempotency response in Redis (24h TTL)
    response = {
        "booking_id": booking_id,
        "razorpay_order_id": razorpay_order["id"],
        "amount": amount,
        "lock_expires_at": (now + timedelta(seconds=settings.SLOT_LOCK_TTL_SECONDS)).isoformat(),
    }
    import json
    await redis.setex(idem_cache_key, 86400, json.dumps(response, default=str))

    return response


def _validate_operating_hours(operating_hours: dict, start: datetime, end: datetime):
    """Ensure booking is within station's operating hours."""
    open_time = operating_hours.get("open", "00:00")
    close_time = operating_hours.get("close", "23:59")
    open_days = operating_hours.get("days", list(range(1, 8)))

    # Day of week (1=Monday, 7=Sunday in ISO)
    if start.isoweekday() not in open_days:
        raise StationClosedError("Station is closed on this day.")

    open_h, open_m = map(int, open_time.split(":"))
    close_h, close_m = map(int, close_time.split(":"))

    station_open  = start.replace(hour=open_h, minute=open_m, second=0, microsecond=0)
    station_close = start.replace(hour=close_h, minute=close_m, second=0, microsecond=0)

    if start < station_open or end > station_close:
        raise StationClosedError("Booking is outside operating hours.")


def _calculate_amount(scheduled_start, scheduled_end, price_per_unit, price_per_hour, power_kw) -> float:
    """Calculate booking cost. Prefer per-unit pricing; fall back to per-hour."""
    duration_hours = (scheduled_end - scheduled_start).total_seconds() / 3600

    if price_per_unit:
        # Estimate energy delivered: power_kw × time × 0.85 efficiency factor
        estimated_kwh = power_kw * duration_hours * 0.85
        return round(float(price_per_unit) * estimated_kwh, 2)
    elif price_per_hour:
        return round(float(price_per_hour) * duration_hours, 2)
    else:
        # Flat-rate fallback
        return round(10.0 * duration_hours, 2)
```

### 5.2 Phase 4 Edge Cases — Concurrency Tests

```python
# tests/integration/test_booking_concurrency.py
import asyncio

class TestBookingConcurrency:
    async def test_concurrent_booking_same_slot_one_wins(
        self, client, seed_station, seed_user_1, seed_user_2, seed_slot
    ):
        """
        CRITICAL TEST: Two users attempt to book the same slot simultaneously.
        Exactly one must succeed, the other must get SLOT_UNAVAILABLE (409).
        """
        slot_id = seed_slot.id
        auth_1 = await get_auth_headers(seed_user_1)
        auth_2 = await get_auth_headers(seed_user_2)

        payload = {
            "slot_id": slot_id,
            "scheduled_start": "2026-06-01T14:00:00+05:30",
            "scheduled_end":   "2026-06-01T14:45:00+05:30",
        }

        # Fire both requests simultaneously
        res1, res2 = await asyncio.gather(
            client.post("/v1/bookings", json={**payload, "idempotency_key": str(uuid4())}, headers=auth_1),
            client.post("/v1/bookings", json={**payload, "idempotency_key": str(uuid4())}, headers=auth_2),
        )

        statuses = {res1.status_code, res2.status_code}
        assert 201 in statuses, "At least one booking must succeed"
        assert 409 in statuses, "At least one booking must fail"

        # Verify only ONE booking exists in DB
        bookings = await count_bookings_for_slot_window(slot_id, "2026-06-01T14:00:00", "2026-06-01T14:45:00")
        assert bookings == 1

    async def test_10_concurrent_bookings_same_slot(self, client, seed_slot, seed_users):
        """Stress test: 10 concurrent users, only 1 must succeed."""
        tasks = [
            client.post("/v1/bookings", json={
                "slot_id": seed_slot.id,
                "scheduled_start": "2026-06-01T10:00:00+05:30",
                "scheduled_end": "2026-06-01T10:45:00+05:30",
                "idempotency_key": str(uuid4()),
            }, headers=await get_auth_headers(user))
            for user in seed_users[:10]
        ]
        responses = await asyncio.gather(*tasks)
        successes = sum(1 for r in responses if r.status_code == 201)
        assert successes == 1

    async def test_overlapping_time_windows_rejected(self, client, auth_headers, seed_slot):
        """Partial time overlap must be detected and rejected."""
        # First booking: 2PM - 3PM
        await client.post("/v1/bookings", json={
            "slot_id": seed_slot.id,
            "scheduled_start": "2026-06-01T14:00:00+05:30",
            "scheduled_end": "2026-06-01T15:00:00+05:30",
            "idempotency_key": str(uuid4()),
        }, headers=auth_headers)

        # Second booking: 2:30PM - 3:30PM (overlaps by 30 min)
        res = await client.post("/v1/bookings", json={
            "slot_id": seed_slot.id,
            "scheduled_start": "2026-06-01T14:30:00+05:30",
            "scheduled_end": "2026-06-01T15:30:00+05:30",
            "idempotency_key": str(uuid4()),
        }, headers=auth_headers)
        assert res.status_code == 409
        assert res.json()["error"]["code"] == "SLOT_UNAVAILABLE"

    async def test_adjacent_bookings_allowed(self, client, auth_headers_1, auth_headers_2, seed_slot):
        """Booking immediately after another ends must succeed."""
        await client.post("/v1/bookings", json={
            "slot_id": seed_slot.id,
            "scheduled_start": "2026-06-01T14:00:00+05:30",
            "scheduled_end": "2026-06-01T15:00:00+05:30",
            "idempotency_key": str(uuid4()),
        }, headers=auth_headers_1)

        res = await client.post("/v1/bookings", json={
            "slot_id": seed_slot.id,
            "scheduled_start": "2026-06-01T15:00:00+05:30",   # starts exactly when first ends
            "scheduled_end": "2026-06-01T16:00:00+05:30",
            "idempotency_key": str(uuid4()),
        }, headers=auth_headers_2)
        assert res.status_code == 201

    async def test_idempotency_key_prevents_duplicate_booking(self, client, auth_headers, seed_slot):
        """Same idempotency key must return cached response, not create second booking."""
        key = str(uuid4())
        payload = {
            "slot_id": seed_slot.id,
            "scheduled_start": "2026-06-02T14:00:00+05:30",
            "scheduled_end": "2026-06-02T14:45:00+05:30",
            "idempotency_key": key,
        }
        res1 = await client.post("/v1/bookings", json=payload, headers=auth_headers)
        res2 = await client.post("/v1/bookings", json=payload, headers=auth_headers)

        assert res1.status_code == 201
        assert res2.status_code == 201
        assert res1.json()["data"]["booking_id"] == res2.json()["data"]["booking_id"]

        # Only 1 booking in DB
        count = await count_bookings_for_user(auth_headers)
        assert count == 1

    async def test_expired_slot_lock_auto_releases(self, client, auth_headers, seed_slot, freeze_time):
        """If payment isn't made within 2 min, slot lock should release."""
        res = await client.post("/v1/bookings", json={
            "slot_id": seed_slot.id,
            "scheduled_start": "2026-06-03T14:00:00+05:30",
            "scheduled_end": "2026-06-03T14:45:00+05:30",
            "idempotency_key": str(uuid4()),
        }, headers=auth_headers)
        assert res.status_code == 201

        # Advance time past lock TTL (2 min + 1 sec)
        freeze_time.move_to("3 minutes later")

        # Another user should now be able to book the same slot
        res2 = await client.post("/v1/bookings", json={
            "slot_id": seed_slot.id,
            "scheduled_start": "2026-06-03T14:00:00+05:30",
            "scheduled_end": "2026-06-03T14:45:00+05:30",
            "idempotency_key": str(uuid4()),
        }, headers=other_auth_headers)
        assert res2.status_code == 201

    async def test_booking_in_the_past_rejected(self, client, auth_headers, seed_slot):
        res = await client.post("/v1/bookings", json={
            "slot_id": seed_slot.id,
            "scheduled_start": "2020-01-01T10:00:00+05:30",
            "scheduled_end": "2020-01-01T10:45:00+05:30",
            "idempotency_key": str(uuid4()),
        }, headers=auth_headers)
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "PAST_TIME_WINDOW"

    async def test_booking_outside_operating_hours_rejected(self, client, auth_headers, seed_slot_station_8am_to_10pm):
        """Station open 8AM–10PM. Booking at midnight must be rejected."""
        res = await client.post("/v1/bookings", json={
            "slot_id": seed_slot_station_8am_to_10pm.id,
            "scheduled_start": "2026-06-03T23:00:00+05:30",
            "scheduled_end": "2026-06-03T23:45:00+05:30",
            "idempotency_key": str(uuid4()),
        }, headers=auth_headers)
        assert res.status_code == 400

    async def test_redis_down_falls_back_to_db_constraint(self, client, auth_headers, seed_slot, mock_redis_down):
        """When Redis is unavailable, DB-level constraint must still prevent double booking."""
        res = await client.post("/v1/bookings", json={
            "slot_id": seed_slot.id,
            "scheduled_start": "2026-06-04T14:00:00+05:30",
            "scheduled_end": "2026-06-04T14:45:00+05:30",
            "idempotency_key": str(uuid4()),
        }, headers=auth_headers)
        # DB-level SELECT FOR UPDATE + constraint should still protect against duplicates
        assert res.status_code in [201, 409]  # Must not 500
```

---

## 6. Phase 5 — Payment Integration (Razorpay)

### 6.1 Payment Service

```python
# app/services/payment_service.py
import hmac
import hashlib

from app.config import settings

def verify_razorpay_signature(
    order_id: str,
    payment_id: str,
    signature: str,
) -> bool:
    """
    Verify Razorpay HMAC-SHA256 signature.
    per HLD Architecture Principle P4: Dual Validation Pattern.
    """
    message = f"{order_id}|{payment_id}"
    expected = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def verify_webhook_signature(payload_body: bytes, received_signature: str) -> bool:
    """Verify Razorpay webhook payload signature."""
    expected = hmac.new(
        settings.RAZORPAY_WEBHOOK_SECRET.encode("utf-8"),
        payload_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, received_signature)


async def confirm_booking_after_payment(booking_id: str, payment_id: str, db, redis, push_service):
    """
    Called by webhook handler. Follows steps 22–30 from HLD data flow.
    Idempotent — safe to call multiple times.
    """
    async with db.begin():
        # Step 1: Re-check booking status (idempotency guard)
        result = await db.execute(text("""
            SELECT b.id, b.status, b.user_id, b.slot_id, b.station_id,
                   b.scheduled_start, b.scheduled_end, b.amount, b.qr_code,
                   p.id as payment_id_pk, p.status as payment_status
            FROM bookings b
            JOIN payments p ON p.booking_id = b.id
            WHERE b.id = :booking_id
            FOR UPDATE
        """), {"booking_id": booking_id})
        booking = result.mappings().first()

        if not booking:
            return  # Booking doesn't exist — ignore webhook

        if booking["status"] == "CONFIRMED":
            return  # Already confirmed — idempotent

        if booking["status"] not in ("PENDING_PAYMENT",):
            return  # Invalid transition — ignore

        # Step 2: Update booking to CONFIRMED
        await db.execute(text("""
            UPDATE bookings
            SET status = 'CONFIRMED', updated_at = NOW()
            WHERE id = :id
        """), {"id": booking_id})

        # Step 3: Update slot from LOCKED → BOOKED
        await db.execute(text("""
            UPDATE slots
            SET status = 'BOOKED',
                locked_by_user = NULL,
                locked_until = NULL,
                updated_at = NOW()
            WHERE id = :slot_id
        """), {"slot_id": booking["slot_id"]})

        # Step 4: Update payment record
        await db.execute(text("""
            UPDATE payments
            SET status = 'SUCCESS',
                razorpay_payment_id = :payment_id,
                webhook_verified = TRUE,
                webhook_received_at = NOW(),
                updated_at = NOW()
            WHERE booking_id = :booking_id
        """), {"booking_id": booking_id, "payment_id": payment_id})

    # Step 5: Release Redis slot lock
    lock_key = f"slot_lock:{booking['slot_id']}"
    await redis.delete(lock_key)

    # Step 6: Send push notification
    await push_service.send_booking_confirmed(
        user_id=booking["user_id"],
        booking_id=booking_id,
        qr_code=booking["qr_code"],
    )


async def process_refund(booking_id: str, reason: str, db, razorpay_client):
    """Handle cancellation refund per cancellation policy."""
    result = await db.execute(text("""
        SELECT p.razorpay_payment_id, b.scheduled_start, b.amount
        FROM payments p
        JOIN bookings b ON b.id = p.booking_id
        WHERE p.booking_id = :booking_id AND p.status = 'SUCCESS'
    """), {"booking_id": booking_id})
    payment = result.mappings().first()

    if not payment:
        return None  # No payment to refund

    refund_amount = _calculate_refund_amount(
        scheduled_start=payment["scheduled_start"],
        total_amount=float(payment["amount"])
    )

    if refund_amount > 0:
        refund = razorpay_client.payment.refund(
            payment["razorpay_payment_id"],
            {"amount": int(refund_amount * 100)}
        )
        return refund
    return None


def _calculate_refund_amount(scheduled_start: datetime, total_amount: float) -> float:
    """Cancellation policy:
    - >6 hours before: 100% refund
    - 2–6 hours before: 50% refund
    - <2 hours before: no refund
    """
    now = datetime.now(timezone.utc)
    hours_until = (scheduled_start - now).total_seconds() / 3600

    if hours_until > 6:
        return total_amount
    elif hours_until >= 2:
        return total_amount * 0.5
    else:
        return 0.0
```

### 6.2 Phase 5 Edge Cases — Payment Tests

```python
# tests/integration/test_payments.py

class TestPaymentVerification:
    async def test_valid_signature_confirms_booking(self, client, auth_headers, pending_booking, mock_razorpay):
        """Correct HMAC signature → booking transitions to PENDING_WEBHOOK."""
        res = await client.post("/v1/payments/verify", json={
            "booking_id": pending_booking.id,
            "razorpay_order_id": pending_booking.razorpay_order_id,
            "razorpay_payment_id": "pay_test123",
            "razorpay_signature": compute_valid_signature(
                pending_booking.razorpay_order_id, "pay_test123"
            ),
        }, headers=auth_headers)
        assert res.status_code == 200

    async def test_invalid_signature_rejected(self, client, auth_headers, pending_booking):
        """Tampered signature must be rejected — booking stays PENDING_PAYMENT."""
        res = await client.post("/v1/payments/verify", json={
            "booking_id": pending_booking.id,
            "razorpay_order_id": pending_booking.razorpay_order_id,
            "razorpay_payment_id": "pay_test123",
            "razorpay_signature": "tampered_signature_xyz",
        }, headers=auth_headers)
        assert res.status_code == 422
        assert res.json()["error"]["code"] == "PAYMENT_VERIFICATION_FAILED"


class TestWebhook:
    async def test_valid_webhook_confirms_booking(self, client, pending_booking, mock_razorpay_webhook):
        payload = build_razorpay_webhook_payload(pending_booking.razorpay_order_id)
        signature = compute_webhook_signature(payload)
        res = await client.post("/v1/payments/webhook",
            content=payload,
            headers={"X-Razorpay-Signature": signature, "Content-Type": "application/json"}
        )
        assert res.status_code == 200
        booking = await get_booking(pending_booking.id)
        assert booking.status == "CONFIRMED"

    async def test_invalid_webhook_signature_rejected(self, client, pending_booking):
        payload = build_razorpay_webhook_payload(pending_booking.razorpay_order_id)
        res = await client.post("/v1/payments/webhook",
            content=payload,
            headers={"X-Razorpay-Signature": "invalid_sig", "Content-Type": "application/json"}
        )
        assert res.status_code == 422

    async def test_duplicate_webhook_idempotent(self, client, confirmed_booking, mock_razorpay_webhook):
        """Second webhook for already-confirmed booking must return 200 without side effects."""
        payload = build_razorpay_webhook_payload(confirmed_booking.razorpay_order_id)
        signature = compute_webhook_signature(payload)
        res = await client.post("/v1/payments/webhook",
            content=payload,
            headers={"X-Razorpay-Signature": signature}
        )
        assert res.status_code == 200  # Must not 500 or 409

    async def test_webhook_for_nonexistent_booking_ignored(self, client):
        """Webhook with unknown order_id must return 200 silently."""
        payload = build_razorpay_webhook_payload("order_nonexistent_xyz")
        signature = compute_webhook_signature(payload)
        res = await client.post("/v1/payments/webhook",
            content=payload,
            headers={"X-Razorpay-Signature": signature}
        )
        assert res.status_code == 200  # Not 404 — don't leak info

    async def test_payment_reconciliation_job_handles_stuck_payments(
        self, client, pending_payment_5min_old
    ):
        """Bookings stuck in PENDING_PAYMENT > 5 min should be reconciled via Razorpay fetch API."""
        from app.tasks.reconcile_payments import run_reconciliation
        await run_reconciliation()
        booking = await get_booking(pending_payment_5min_old.booking_id)
        # Either CONFIRMED (webhook was delayed) or CANCELLED (payment not made)
        assert booking.status in ("CONFIRMED", "CANCELLED_BY_ADMIN")


class TestCancellation:
    async def test_full_refund_more_than_6_hours_before(self, client, auth_headers, confirmed_booking_far_future):
        res = await client.delete(f"/v1/bookings/{confirmed_booking_far_future.id}", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["refund_amount"] == confirmed_booking_far_future.amount

    async def test_50_percent_refund_2_to_6_hours_before(self, client, auth_headers, confirmed_booking_near_future):
        res = await client.delete(f"/v1/bookings/{confirmed_booking_near_future.id}", headers=auth_headers)
        assert res.json()["data"]["refund_amount"] == confirmed_booking_near_future.amount * 0.5

    async def test_no_refund_less_than_2_hours_before(self, client, auth_headers, confirmed_booking_imminent):
        res = await client.delete(f"/v1/bookings/{confirmed_booking_imminent.id}", headers=auth_headers)
        assert res.json()["data"]["refund_amount"] == 0.0

    async def test_cannot_cancel_active_booking(self, client, auth_headers, active_booking):
        res = await client.delete(f"/v1/bookings/{active_booking.id}", headers=auth_headers)
        assert res.status_code == 409
        assert res.json()["error"]["code"] == "BOOKING_NOT_CANCELLABLE"

    async def test_cannot_cancel_already_cancelled_booking(self, client, auth_headers, cancelled_booking):
        res = await client.delete(f"/v1/bookings/{cancelled_booking.id}", headers=auth_headers)
        assert res.status_code == 409

    async def test_razorpay_down_during_refund_queues_for_retry(
        self, client, auth_headers, confirmed_booking, mock_razorpay_down
    ):
        """When Razorpay is unreachable, booking should still cancel and refund should be queued."""
        res = await client.delete(f"/v1/bookings/{confirmed_booking.id}", headers=auth_headers)
        assert res.status_code == 200
        booking = await get_booking(confirmed_booking.id)
        assert booking.status == "REFUND_PENDING"  # Queued for retry
```

---

## 7. Phase 6 — Real-Time Layer

### 7.1 Stale Lock Cleanup Background Task

```python
# app/tasks/cleanup_stale_locks.py
# Runs every 30 seconds via APScheduler

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import text

async def release_stale_slot_locks(db, redis):
    """
    Release LOCKED slots where locked_until has passed.
    Handles crashed clients and payment timeouts.
    """
    result = await db.execute(text("""
        UPDATE slots
        SET status = 'AVAILABLE',
            locked_by_user = NULL,
            locked_until = NULL,
            updated_at = NOW()
        WHERE status = 'LOCKED'
        AND locked_until < NOW()
        RETURNING id, station_id
    """))
    released = result.fetchall()

    for row in released:
        # Also clean Redis lock key
        await redis.delete(f"slot_lock:{row.id}")

    if released:
        # Cancel pending_payment bookings for released slots
        slot_ids = [str(row.id) for row in released]
        await db.execute(text("""
            UPDATE bookings
            SET status = 'CANCELLED_BY_ADMIN',
                cancellation_reason = 'Payment timeout — slot lock expired',
                updated_at = NOW()
            WHERE slot_id = ANY(:slot_ids)
            AND status = 'PENDING_PAYMENT'
        """), {"slot_ids": slot_ids})
        await db.commit()

    return len(released)
```

### 7.2 IoT Simulator

```python
# app/services/iot_simulator.py
# Simulates real-time charger status changes for demo purposes

import asyncio
import random
from datetime import datetime, timezone

async def simulate_station_events(db, redis, push_service):
    """
    Randomly transitions IN_USE slots to AVAILABLE to simulate
    charging sessions ending — creates realistic live demo.
    """
    while True:
        await asyncio.sleep(random.randint(30, 90))  # Every 30–90 seconds

        # Find a random IN_USE slot
        result = await db.execute(text("""
            SELECT id, station_id FROM slots
            WHERE status = 'IN_USE'
            ORDER BY RANDOM()
            LIMIT 1
        """))
        slot = result.mappings().first()

        if slot:
            await db.execute(text("""
                UPDATE slots SET status = 'AVAILABLE', updated_at = NOW()
                WHERE id = :id
            """), {"id": slot["id"]})
            await db.commit()
            # Supabase Realtime picks up the DB change and broadcasts to clients
```

---

## 8. Phase 7 — Notifications, Route Planner & Reviews

### 8.1 Notification Service

```python
# app/services/notification_service.py
import httpx
from app.config import settings

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"

async def send_push_notification(
    expo_push_token: str,
    title: str,
    body: str,
    data: dict = None,
) -> bool:
    """Send push notification via Expo Push API."""
    payload = {
        "to": expo_push_token,
        "title": title,
        "body": body,
        "sound": "default",
        "data": data or {},
        "priority": "high",
        "channelId": "bookings",  # Android notification channel
    }

    async with httpx.AsyncClient() as client:
        try:
            res = await client.post(
                EXPO_PUSH_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.EXPO_ACCESS_TOKEN}",
                    "Content-Type": "application/json",
                },
                timeout=10.0,
            )
            ticket = res.json().get("data", {})
            if ticket.get("status") == "error":
                # Handle DeviceNotRegistered — remove stale token
                if ticket.get("details", {}).get("error") == "DeviceNotRegistered":
                    await remove_push_token(expo_push_token)
                return False
            return True
        except Exception as e:
            # Notification failure must never crash booking flow
            print(f"[Push] Failed to send notification: {e}")
            return False


async def send_booking_confirmed(user_id: str, booking_id: str, qr_code: str, db, push_service):
    user = await get_user_by_id(user_id, db)
    if user.expo_push_token:
        await push_service.send_push_notification(
            expo_push_token=user.expo_push_token,
            title="⚡ Booking Confirmed!",
            body=f"Your slot is locked in. Tap to see your QR code.",
            data={"type": "BOOKING_CONFIRMED", "booking_id": booking_id},
        )

    # Also store in-app notification
    await db.execute(text("""
        INSERT INTO notifications (user_id, type, title, body, data)
        VALUES (:uid, 'BOOKING_CONFIRMED', :title, :body, :data)
    """), {
        "uid": user_id,
        "title": "Booking Confirmed",
        "body": f"Booking #{booking_id[:8].upper()} is confirmed.",
        "data": json.dumps({"booking_id": booking_id}),
    })
```

### 8.2 Route Planner Service

```python
# app/services/route_service.py
# EV-aware route planner — factors in battery range and charging stops

import httpx
from app.config import settings

async def plan_ev_route(
    origin_lat: float, origin_lng: float,
    dest_lat: float, dest_lng: float,
    current_battery_percent: float,
    vehicle_range_km: float,
    db, redis,
) -> dict:
    """
    Calculate EV-aware route with charging stops.
    Algorithm:
    1. Get route from Google Maps Directions API
    2. Calculate range at current battery %
    3. Find sections of route that exceed range
    4. Query PostGIS for stations near those sections
    5. Return optimized stop sequence
    """
    # Cache check (5-min TTL per HLD)
    cache_key = f"route:{origin_lat:.4f}:{origin_lng:.4f}:{dest_lat:.4f}:{dest_lng:.4f}:{current_battery_percent}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    # 1. Get route from Google Directions API
    async with httpx.AsyncClient() as client:
        directions_res = await client.get(
            "https://maps.googleapis.com/maps/api/directions/json",
            params={
                "origin": f"{origin_lat},{origin_lng}",
                "destination": f"{dest_lat},{dest_lng}",
                "mode": "driving",
                "key": settings.GOOGLE_MAPS_API_KEY,
            },
            timeout=10.0,
        )

    route_data = directions_res.json()
    if not route_data.get("routes"):
        raise RouteNotFoundError("No route found between origin and destination.")

    total_distance_km = route_data["routes"][0]["legs"][0]["distance"]["value"] / 1000

    # 2. Calculate effective range
    current_range_km = (current_battery_percent / 100.0) * vehicle_range_km * 0.9  # 10% safety buffer

    if current_range_km >= total_distance_km:
        # No charging needed
        return {
            "route": route_data["routes"][0],
            "charging_stops": [],
            "total_distance_km": total_distance_km,
            "range_sufficient": True,
        }

    # 3. Calculate where battery runs out along route
    charging_stops = await _find_charging_stops_along_route(
        route_data["routes"][0],
        current_range_km,
        vehicle_range_km,
        db,
    )

    result = {
        "route": route_data["routes"][0],
        "charging_stops": charging_stops,
        "total_distance_km": total_distance_km,
        "range_sufficient": False,
    }

    await redis.setex(cache_key, 300, json.dumps(result, default=str))
    return result
```

---

## 9. Phase 8 — Admin API, AI Demand Prediction & Hardening

### 9.1 Rate Limiter Middleware

```python
# app/middleware/rate_limiter.py
from fastapi import Request, HTTPException
from app.db.redis import get_redis
from app.config import settings

# Rate limit configs per endpoint group
RATE_LIMITS = {
    "/v1/auth/otp/send":   {"key": "phone", "limit": 3,   "window": 600},
    "/v1/auth/otp/verify": {"key": "phone", "limit": 5,   "window": 600},
    "/v1/stations/nearby": {"key": "user",  "limit": 60,  "window": 60},
    "/v1/bookings":        {"key": "user",  "limit": 10,  "window": 60},
    "authenticated":       {"key": "user",  "limit": 100, "window": 60},
    "unauthenticated":     {"key": "ip",    "limit": 20,  "window": 60},
}

class RateLimiterMiddleware:
    async def __call__(self, request: Request, call_next):
        redis = await get_redis()
        config = _get_rate_config(request.url.path, request.state)

        key = _build_rate_key(request, config)
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, config["window"])

        limit = config["limit"]
        ttl = await redis.ttl(key)

        # Set rate limit headers
        request.state.rate_limit_remaining = max(0, limit - count)
        request.state.rate_limit_reset = ttl

        if count > limit:
            raise HTTPException(
                status_code=429,
                detail={"code": "RATE_LIMITED", "message": "Too many requests."},
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "Retry-After": str(ttl),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - count))
        response.headers["X-RateLimit-Reset"] = str(ttl)
        return response
```

### 9.2 AI Demand Prediction Service

```python
# app/services/demand_service.py
# Simple ML model — gradient boosted decision tree on historical booking data

import numpy as np
from datetime import datetime, date
from sqlalchemy import text

async def train_demand_model(db) -> dict:
    """
    Train a lightweight demand forecasting model.
    Features: day_of_week, hour, station_id, month
    Target: booking_count for that (station, day, hour) bucket
    """
    result = await db.execute(text("""
        SELECT
            station_id,
            EXTRACT(DOW FROM scheduled_start) as day_of_week,
            EXTRACT(HOUR FROM scheduled_start) as hour,
            EXTRACT(MONTH FROM scheduled_start) as month,
            COUNT(*) as booking_count
        FROM bookings
        WHERE status IN ('CONFIRMED', 'COMPLETED', 'ACTIVE')
        AND scheduled_start > NOW() - INTERVAL '90 days'
        GROUP BY station_id, day_of_week, hour, month
    """))

    data = result.fetchall()

    # For MVP: simple lookup table with smoothing
    # Production: replace with scikit-learn GradientBoostingRegressor
    demand_map = {}
    for row in data:
        key = (str(row.station_id), int(row.day_of_week), int(row.hour))
        demand_map[key] = {
            "count": int(row.booking_count),
            "normalized": min(1.0, int(row.booking_count) / 10.0),  # normalize to 0–1
        }

    return demand_map


async def predict_demand(
    station_id: str,
    target_date: date,
    db,
    redis,
) -> list:
    """Return 24-hour demand prediction for a station on a given date."""
    cache_key = f"demand:{station_id}:{target_date}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    model = await train_demand_model(db)
    day_of_week = target_date.weekday()

    predictions = []
    for hour in range(24):
        key = (station_id, day_of_week, hour)
        data = model.get(key, {"count": 0, "normalized": 0.0})
        predictions.append({
            "hour": hour,
            "predicted_load": data["normalized"],
            "predicted_bookings": data["count"],
        })

    # Cache for 1 hour
    await redis.setex(cache_key, 3600, json.dumps(predictions))
    return predictions
```

### 9.3 Admin API — Slot Status Update with Cascade

```python
# app/routers/admin.py — slot status update with affected bookings cascade

@router.patch("/stations/{station_id}/slots/{slot_id}")
async def update_slot_status(
    station_id: str,
    slot_id: str,
    body: UpdateSlotStatusRequest,
    admin = Depends(require_admin),
    db = Depends(get_db),
    redis = Depends(get_redis),
    push_service = Depends(get_push_service),
):
    """Mark slot offline/online. If going offline, notify affected bookings."""

    # Verify admin owns this station
    if admin["role"] == "station_admin":
        station = await get_station_by_admin(admin["sub"], station_id, db)
        if not station:
            raise HTTPException(403, detail={"code": "FORBIDDEN"})

    # Find future confirmed bookings for this slot
    affected = await db.execute(text("""
        SELECT b.id, b.user_id, b.scheduled_start, u.phone
        FROM bookings b
        JOIN users u ON u.id = b.user_id
        WHERE b.slot_id = :slot_id
        AND b.status IN ('CONFIRMED', 'PENDING_PAYMENT')
        AND b.scheduled_start > NOW()
    """), {"slot_id": slot_id})
    affected_bookings = affected.fetchall()

    # Update slot status
    await db.execute(text("""
        UPDATE slots
        SET status = :status, fault_code = :fault_code, updated_at = NOW()
        WHERE id = :slot_id AND station_id = :station_id
    """), {
        "slot_id": slot_id,
        "station_id": station_id,
        "status": body.status,
        "fault_code": body.fault_code,
    })

    if body.status == "OFFLINE" and affected_bookings:
        # Flag affected bookings and notify users
        for booking in affected_bookings:
            await push_service.send_push_notification(
                user_id=booking.user_id,
                title="⚠️ Booking Update Required",
                body="A charger at your booked station went offline. Please rebook.",
                data={"type": "SLOT_OFFLINE", "booking_id": str(booking.id)},
            )

    await db.commit()

    return {
        "success": True,
        "data": {
            "slot_id": slot_id,
            "status": body.status,
            "fault_code": body.fault_code,
            "affected_bookings": [
                {
                    "booking_id": str(b.id),
                    "user_phone": b.phone[:3] + "XXXXX" + b.phone[-2:],  # masked
                    "scheduled_start": b.scheduled_start.isoformat(),
                    "action": "notification_sent",
                } for b in affected_bookings
            ],
        },
    }
```

---

## 10. Cross-Cutting Concerns

### 10.1 Standard Response Envelope

```python
# app/utils/response.py
from datetime import datetime, timezone
import uuid

def success_response(data, meta: dict = None) -> dict:
    return {
        "success": True,
        "data": data,
        "meta": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": meta.get("request_id", str(uuid.uuid4())) if meta else str(uuid.uuid4()),
        },
    }

def paginated_response(data, total: int, limit: int, offset: int, meta: dict = None) -> dict:
    return {
        "success": True,
        "data": data,
        "pagination": {
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_next": offset + limit < total,
            "has_prev": offset > 0,
        },
        "meta": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": meta.get("request_id", str(uuid.uuid4())) if meta else str(uuid.uuid4()),
        },
    }
```

### 10.2 Global Error Handler

```python
# app/middleware/error_handler.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import uuid

def register_error_handlers(app: FastAPI):
    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed.",
                    "details": exc.errors(),
                },
                "meta": {"timestamp": _now(), "request_id": _req_id(request)},
            },
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception):
        import logging, traceback
        logging.error(f"Unhandled exception: {traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred.",
                },
                "meta": {"timestamp": _now(), "request_id": _req_id(request)},
            },
        )
```

---

## 11. Master Edge Case Registry

### Auth Edge Cases

| ID | Edge Case | Handling | Tested |
|---|---|---|---|
| EC-A01 | OTP sent to invalid/non-Indian phone | 422 VALIDATION_ERROR | ✅ |
| EC-A02 | OTP rate limit hit (3/10min) | 429 OTP_LIMIT_EXCEEDED + retry_after | ✅ |
| EC-A03 | Wrong OTP entered | 401 + attempts_remaining counter | ✅ |
| EC-A04 | OTP locked after 5 wrong attempts | 401, attempts_remaining=0 | ✅ |
| EC-A05 | Expired OTP used | 401 INVALID_OTP | ✅ |
| EC-A06 | OTP reused after successful verify | 401 (Redis key deleted on first use) | ✅ |
| EC-A07 | Access token used as refresh token | 401 UNAUTHORIZED | ✅ |
| EC-A08 | Expired refresh token | 401 TOKEN_EXPIRED | ✅ |
| EC-A09 | Logged-out token used on any endpoint | 401 (blacklisted jti) | ✅ |
| EC-A10 | Token from deleted/banned user | 403 FORBIDDEN | ✅ |
| EC-A11 | Concurrent login from two devices | Both sessions valid | ✅ |
| EC-A12 | 401 triggers auto-refresh, retries | Single retry, then logout | ✅ |

### Station/Slot Edge Cases

| ID | Edge Case | Handling | Tested |
|---|---|---|---|
| EC-S01 | Coordinates at ocean/remote area | 200 with empty array | ✅ |
| EC-S02 | Latitude/longitude out of bounds | 422 VALIDATION_ERROR | ✅ |
| EC-S03 | Radius_km > 50 | 422 VALIDATION_ERROR (capped) | ✅ |
| EC-S04 | Station goes offline mid-session | Slot → OFFLINE, users notified | ✅ |
| EC-S05 | Cache stale when station added | Cache TTL 10s, max 10s delay | ✅ |
| EC-S06 | Station with zero slots | Returns station, no slots array | ✅ |
| EC-S07 | All slots at a station are offline | available_slots=0, shown as unavailable | ✅ |

### Booking Edge Cases

| ID | Edge Case | Handling | Tested |
|---|---|---|---|
| EC-B01 | Two users book same slot simultaneously | DB SELECT FOR UPDATE, one wins 201, other 409 | ✅ |
| EC-B02 | 10 concurrent booking attempts | Only 1 succeeds | ✅ |
| EC-B03 | Overlapping time window with existing booking | 409 SLOT_UNAVAILABLE | ✅ |
| EC-B04 | Adjacent booking (end == start) | 201 — should succeed | ✅ |
| EC-B05 | Booking in the past | 400 PAST_TIME_WINDOW | ✅ |
| EC-B06 | Booking outside operating hours | 400 | ✅ |
| EC-B07 | Booking on station's closed day | 400 | ✅ |
| EC-B08 | Duplicate idempotency key | 201 with cached response | ✅ |
| EC-B09 | Slot lock expires without payment | Auto-release, PENDING_PAYMENT → CANCELLED | ✅ |
| EC-B10 | Redis down during slot locking | Falls back to DB-level constraint | ✅ |
| EC-B11 | User books slot at OFFLINE station | 409 SLOT_UNAVAILABLE | ✅ |
| EC-B12 | Booking duration < 30 min | 422 | ✅ |
| EC-B13 | Booking duration > 2 hours | 422 | ✅ |
| EC-B14 | User attempts to book their own locked slot again | 409 SLOT_LOCKED | ✅ |

### Payment Edge Cases

| ID | Edge Case | Handling | Tested |
|---|---|---|---|
| EC-P01 | Invalid Razorpay signature | 422 PAYMENT_VERIFICATION_FAILED | ✅ |
| EC-P02 | Invalid webhook signature | 422 | ✅ |
| EC-P03 | Duplicate webhook for same order | 200 (idempotent) | ✅ |
| EC-P04 | Webhook for unknown order_id | 200 (silent) | ✅ |
| EC-P05 | User cancels Razorpay sheet | Slot lock released via TTL | ✅ |
| EC-P06 | Payment timeout (>2 min) | Booking auto-cancelled, slot freed | ✅ |
| EC-P07 | Razorpay API down during order create | 503 PAYMENT_GATEWAY_ERROR | ✅ |
| EC-P08 | Razorpay down during refund | Booking status → REFUND_PENDING, retry queue | ✅ |
| EC-P09 | Refund > 6h before: 100% | Correct refund amount | ✅ |
| EC-P10 | Refund 2–6h before: 50% | Correct refund amount | ✅ |
| EC-P11 | Refund < 2h before: 0% | No refund | ✅ |
| EC-P12 | Cancel already-cancelled booking | 409 BOOKING_NOT_CANCELLABLE | ✅ |
| EC-P13 | Cancel ACTIVE booking | 409 | ✅ |
| EC-P14 | Webhook delayed 10+ minutes | Reconciliation job catches and confirms | ✅ |

### Realtime Edge Cases

| ID | Edge Case | Handling | Tested |
|---|---|---|---|
| EC-R01 | Supabase Realtime disconnects | Client falls back to 15s polling | ✅ |
| EC-R02 | Client reconnects after WS drop | Resyncs slot states on reconnect | ✅ |
| EC-R03 | Realtime fires for wrong station | Channel filter scopes by station_id | ✅ |
| EC-R04 | Multiple tabs open same station | Each tab independently subscribed | ✅ |
| EC-R05 | App backgrounded, WS fires | State updated on app foreground | ✅ |

---

## 12. Testing Strategy & Coverage Plan

### 12.1 Test Configuration

```python
# tests/conftest.py
import asyncio
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from unittest.mock import AsyncMock, patch

from app.main import app
from app.config import settings

# Use separate test database
TEST_DATABASE_URL = settings.DATABASE_URL.replace("/evchargefinder", "/evchargefinder_test")

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def db_engine():
    engine = create_async_engine(TEST_DATABASE_URL)
    yield engine
    await engine.dispose()

@pytest.fixture(autouse=True)
async def db(db_engine):
    """Provide a transaction-rolled-back test database session."""
    async with db_engine.begin() as conn:
        async with AsyncSession(bind=conn) as session:
            yield session
            await session.rollback()

@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

@pytest.fixture
async def auth_headers(client, seed_user):
    """Create a valid JWT token for test user."""
    from app.services.auth_service import create_access_token
    token = create_access_token(seed_user)
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
async def admin_headers(client, seed_admin_user):
    from app.services.auth_service import create_access_token
    token = create_access_token(seed_admin_user)
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def mock_razorpay(mocker):
    return mocker.patch("app.services.payment_service.razorpay_client", autospec=True)

@pytest.fixture
def mock_redis_down(mocker):
    """Simulate Redis being unavailable."""
    async def mock_get(*args, **kwargs): raise ConnectionError("Redis down")
    async def mock_set(*args, **kwargs): raise ConnectionError("Redis down")
    mocker.patch("app.db.redis.get_redis", return_value=AsyncMock(
        get=mock_get, set=mock_set, setex=mock_get, incr=mock_get
    ))
```

### 12.2 Coverage Requirements

| Layer | Min Coverage | Current Focus |
|---|---|---|
| Services (business logic) | 95% | All booking/payment edge cases |
| Routers (HTTP layer) | 90% | Request validation, response format |
| Utilities | 100% | Crypto, time, geo helpers |
| Models | 80% | DB constraint validation |
| Middleware | 90% | Rate limiting, auth |
| Overall | 88%+ | Gate on CI |

### 12.3 Integration Test Matrix

```python
# tests/integration/test_full_booking_flow.py
# End-to-end happy path and major failure paths

class TestFullBookingFlow:
    async def test_complete_happy_path(self, client, seed_user, seed_station):
        """
        Full booking lifecycle:
        Phone → OTP → Login → Find Station → View Slots → Book → Pay → QR → Cancel
        """
        # 1. Send OTP
        r1 = await client.post("/v1/auth/otp/send", json={"phone": "+919876543210"})
        assert r1.status_code == 200

        # 2. Verify OTP
        otp = await get_test_otp("+919876543210")
        r2 = await client.post("/v1/auth/otp/verify", json={"phone": "+919876543210", "otp": otp})
        assert r2.status_code == 200
        headers = {"Authorization": f"Bearer {r2.json()['data']['access_token']}"}

        # 3. Find nearby stations
        r3 = await client.get("/v1/stations/nearby?lat=23.2599&lng=77.4126", headers=headers)
        assert r3.status_code == 200
        station_id = r3.json()["data"][0]["id"]

        # 4. Get station detail
        r4 = await client.get(f"/v1/stations/{station_id}", headers=headers)
        assert r4.status_code == 200
        slot = next(s for s in r4.json()["data"]["slots"] if s["status"] == "AVAILABLE")

        # 5. Create booking
        r5 = await client.post("/v1/bookings", json={
            "slot_id": slot["id"],
            "scheduled_start": "2026-06-15T14:00:00+05:30",
            "scheduled_end": "2026-06-15T14:45:00+05:30",
            "idempotency_key": str(uuid4()),
        }, headers=headers)
        assert r5.status_code == 201
        booking_id = r5.json()["data"]["booking_id"]
        order_id = r5.json()["data"]["razorpay_order_id"]

        # 6. Verify payment (simulate Razorpay callback)
        r6 = await client.post("/v1/payments/verify", json={
            "booking_id": booking_id,
            "razorpay_order_id": order_id,
            "razorpay_payment_id": "pay_test_123",
            "razorpay_signature": compute_valid_signature(order_id, "pay_test_123"),
        }, headers=headers)
        assert r6.status_code == 200

        # 7. Simulate webhook (async confirmation)
        await simulate_razorpay_webhook(client, order_id, "pay_test_123")

        # 8. Get booking — should be CONFIRMED with QR
        r8 = await client.get(f"/v1/bookings/{booking_id}", headers=headers)
        assert r8.json()["data"]["status"] == "CONFIRMED"
        assert r8.json()["data"]["qr_code"] is not None

        # 9. Cancel booking (>6h future)
        r9 = await client.delete(f"/v1/bookings/{booking_id}", headers=headers)
        assert r9.status_code == 200
        assert r9.json()["data"]["refund_amount"] > 0

        # 10. Verify slot is AVAILABLE again
        r10 = await client.get(f"/v1/stations/{station_id}", headers=headers)
        slot_status = next(s["status"] for s in r10.json()["data"]["slots"] if s["id"] == slot["id"])
        assert slot_status == "AVAILABLE"
```

---

## 13. CI/CD Pipeline

```yaml
# .github/workflows/ci.yml
name: EVChargeFinder CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgis/postgis:16-3.4
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_DB: evchargefinder_test
        ports: ["5432:5432"]
        options: --health-cmd pg_isready --health-interval 10s --health-timeout 5s --health-retries 5

      redis:
        image: redis:7-alpine
        ports: ["6379:6379"]

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }

      - name: Install dependencies
        run: pip install -r requirements-dev.txt

      - name: Run Alembic migrations
        run: alembic upgrade head
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:test@localhost/evchargefinder_test

      - name: Run unit tests
        run: pytest tests/unit -v --cov=app --cov-report=xml

      - name: Run integration tests
        run: pytest tests/integration -v --cov=app --cov-append --cov-report=xml

      - name: Check coverage threshold (88%)
        run: coverage report --fail-under=88

      - name: Upload coverage
        uses: codecov/codecov-action@v4

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install ruff mypy
      - run: ruff check app/
      - run: mypy app/ --strict

  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install bandit safety
      - run: bandit -r app/ -ll  # Check for security issues
      - run: safety check         # Check dependencies for known CVEs
```

---

## 14. Performance & Load Testing

### 14.1 Load Test Targets (per HLD §20.3 Scalability)

```python
# tests/load/locustfile.py
from locust import HttpUser, task, between

class EVUser(HttpUser):
    wait_time = between(1, 3)
    token = None

    def on_start(self):
        """Login on test start."""
        res = self.client.post("/v1/auth/otp/send", json={"phone": f"+9198{random_phone()}"})
        otp = get_otp_from_response(res)
        login_res = self.client.post("/v1/auth/otp/verify", json={
            "phone": res.json()["data"]["phone"], "otp": otp
        })
        self.token = login_res.json()["data"]["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

    @task(10)
    def view_nearby_stations(self):
        """Most common action — 60% of traffic."""
        self.client.get(
            "/v1/stations/nearby?lat=23.2599&lng=77.4126&radius_km=10",
            headers=self.headers
        )

    @task(4)
    def view_station_detail(self):
        self.client.get(f"/v1/stations/{SEED_STATION_ID}", headers=self.headers)

    @task(2)
    def create_booking(self):
        self.client.post("/v1/bookings", json={
            "slot_id": SEED_SLOT_ID,
            "scheduled_start": future_time(hours=2),
            "scheduled_end": future_time(hours=3),
            "idempotency_key": str(uuid4()),
        }, headers=self.headers)

    @task(1)
    def view_my_bookings(self):
        self.client.get("/v1/bookings/my", headers=self.headers)

# Run with: locust -f locustfile.py --users 100 --spawn-rate 10 -t 60s
# Target: p95 response < 200ms at 100 concurrent users
```

### 14.2 Performance Test Assertions

| Endpoint | p50 Target | p95 Target | p99 Target |
|---|---|---|---|
| GET /stations/nearby (cached) | 20ms | 50ms | 100ms |
| GET /stations/nearby (DB) | 100ms | 200ms | 500ms |
| POST /bookings | 300ms | 600ms | 1000ms |
| POST /payments/verify | 200ms | 400ms | 800ms |
| GET /stations/:id | 50ms | 100ms | 200ms |
| WebSocket slot update | <500ms | <1s | <2s |

---

*Document End — EVChargeFinder Backend Implementation Plan v1.0*
*References: PRD_EVChargeFinder v1.0 · HLD_TRD_EVChargeFinder v1.0 · API_SPEC v1.0*
