# High-Level Design + Technical Reference Document
## EVChargeFinder — Intelligent EV Charging Station Locator & Slot Booking System

---

| Field | Details |
|---|---|
| **Document Version** | v1.0 |
| **Document Type** | HLD + TRD (Mixed) |
| **Status** | Draft |
| **Author** | Shubhranshu Das (Reesh) |
| **Date** | April 2026 |
| **Reference PRD** | PRD_EVChargeFinder v1.0 |

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture Principles](#2-architecture-principles)
3. [System Architecture Diagram](#3-system-architecture-diagram)
4. [Component Breakdown](#4-component-breakdown)
5. [Technology Stack — Justified](#5-technology-stack--justified)
6. [Database Design (Supabase + PostgreSQL + PostGIS)](#6-database-design-supabase--postgresql--postgis)
7. [API Design Specification](#7-api-design-specification)
8. [Real-Time Architecture (WebSocket + Supabase Realtime)](#8-real-time-architecture-websocket--supabase-realtime)
9. [Slot Booking & Concurrency Control](#9-slot-booking--concurrency-control)
10. [Authentication & Authorization](#10-authentication--authorization)
11. [Payment Architecture (Razorpay)](#11-payment-architecture-razorpay)
12. [Geospatial Query Design](#12-geospatial-query-design)
13. [Notification Architecture](#13-notification-architecture)
14. [AI Demand Prediction Module](#14-ai-demand-prediction-module)
15. [Admin Dashboard Architecture](#15-admin-dashboard-architecture)
16. [Caching Strategy](#16-caching-strategy)
17. [Security Architecture](#17-security-architecture)
18. [Observability & Monitoring](#18-observability--monitoring)
19. [Deployment Architecture](#19-deployment-architecture)
20. [Scalability & Failure Analysis](#20-scalability--failure-analysis)
21. [Data Flow Diagrams](#21-data-flow-diagrams)
22. [OCPP Integration Layer (Future-Ready)](#22-ocpp-integration-layer-future-ready)

---

## 1. System Overview

EVChargeFinder is a **multi-tenant, event-driven, real-time SaaS platform** that aggregates EV charging infrastructure across India into a single unified layer — enabling discovery, real-time availability monitoring, advance slot reservation, UPI payment, and EV-aware route planning.

### 1.1 Core Architectural Style

```
┌─────────────────────────────────────────────────────────────────┐
│                    ARCHITECTURAL STYLE                          │
│                                                                 │
│  Client Layer    →   API Gateway   →   Microservices-lite       │
│  (React Native)      (FastAPI)         (Domain-separated        │
│                                         service modules)        │
│                                                                 │
│  Event Layer     →   Supabase Realtime  →  WebSocket Clients    │
│  (Postgres CDC)                                                 │
│                                                                 │
│  Data Layer      →   Supabase (PostgreSQL + PostGIS)            │
│                  →   Redis (Cache + Distributed Locks)          │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 System Boundaries

| Boundary | Description |
|---|---|
| **Internal** | React Native App, FastAPI Backend, Supabase DB, Redis Cache, Admin Dashboard |
| **External** | Google Maps Platform, MapmyIndia, Razorpay, Expo Push Notifications, Simulated IoT Feed |
| **Future** | OCPP Charger Hardware, EV OEM APIs (Tata Motors Connect, Ather Connect) |

---

## 2. Architecture Principles

These are the **non-negotiable engineering tenets** that every design decision in this system is evaluated against:

### P1 — Consistency Over Availability for Bookings
For the slot booking subsystem, we choose **CP (Consistency + Partition Tolerance)** over AP. A user must never receive a double-booked slot confirmation. We trade slight availability degradation under partition for guaranteed booking integrity.

### P2 — Eventual Consistency for Station Discovery
Station availability display is **eventually consistent** (AP). A 2–5 second lag in slot status is acceptable for the map discovery view. This allows high read throughput without locking overhead.

### P3 — Idempotency for All Mutating Operations
Every booking, payment, and cancellation API endpoint must be **idempotent**. Clients must supply an `idempotency_key` (UUID v4) to prevent duplicate operations on retry.

### P4 — Defense in Depth for Payments
Payment confirmation follows a **dual-validation pattern**: client-side Razorpay callback + server-side webhook verification. A booking is only marked `CONFIRMED` when both signals are received and signature-verified.

### P5 — Geo-First Data Modeling
All location data uses **PostGIS geography types** with GIST spatial indexes. No application-layer bounding box math — all radius queries execute at the database layer.

### P6 — Stateless API Layer
The FastAPI service layer is **fully stateless**. All session state lives in JWT tokens (short-lived, 15-min access tokens + 7-day refresh tokens). This enables horizontal scaling with zero sticky sessions.

### P7 — OCPP-Aware from Day One
Internal domain models map to OCPP 2.0.1 concepts (EVSE, Connector, ChargingStation) even though hardware integration is out of scope for MVP. This prevents schema migrations when real hardware is connected.

---

## 3. System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                       │
│                                                                                 │
│   ┌─────────────────────┐              ┌──────────────────────────┐             │
│   │  React Native App   │              │   Admin Dashboard        │             │
│   │  (Expo — iOS/Android│              │   (Next.js Web)          │             │
│   │                     │              │                          │             │
│   │  • Map View         │              │  • Station Management    │             │
│   │  • Booking Flow     │              │  • Analytics             │             │
│   │  • Route Planner    │              │  • Live Monitoring       │             │
│   │  • Payment          │              │  • Demand Heatmap        │             │
│   └──────────┬──────────┘              └────────────┬─────────────┘             │
└──────────────│─────────────────────────────────────│─────────────────────────────┘
               │  HTTPS / WSS                        │  HTTPS
               ▼                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              API GATEWAY LAYER                                  │
│                                                                                 │
│   ┌──────────────────────────────────────────────────────────────────────┐      │
│   │                    FastAPI Application Server                        │      │
│   │                    (Uvicorn + Gunicorn Workers)                      │      │
│   │                                                                      │      │
│   │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │      │
│   │  │  Auth Router │  │ Station      │  │  Booking     │               │      │
│   │  │  /v1/auth    │  │ Router       │  │  Router      │               │      │
│   │  │              │  │ /v1/stations │  │  /v1/bookings│               │      │
│   │  └──────────────┘  └──────────────┘  └──────────────┘               │      │
│   │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │      │
│   │  │  Payment     │  │  Route       │  │  Admin       │               │      │
│   │  │  Router      │  │  Router      │  │  Router      │               │      │
│   │  │  /v1/payments│  │  /v1/routes  │  │  /v1/admin   │               │      │
│   │  └──────────────┘  └──────────────┘  └──────────────┘               │      │
│   │                                                                      │      │
│   │  ┌───────────────────────────────────────────────────────────┐      │      │
│   │  │              Middleware Stack                              │      │      │
│   │  │  JWT Verify → Rate Limiter → CORS → Request Logger        │      │      │
│   │  └───────────────────────────────────────────────────────────┘      │      │
│   └──────────────────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────────────────┘
               │                    │                    │
               ▼                    ▼                    ▼
┌──────────────────┐  ┌─────────────────────┐  ┌──────────────────────────────┐
│   CACHE LAYER    │  │   DATA LAYER         │  │   EXTERNAL SERVICES          │
│                  │  │                     │  │                              │
│  Redis           │  │  Supabase           │  │  • Google Maps Platform      │
│                  │  │  (PostgreSQL        │  │  • MapmyIndia API            │
│  • Slot locks    │  │   + PostGIS)        │  │  • Razorpay Payment Gateway  │
│  • Station cache │  │                     │  │  • Expo Push Notifications   │
│  • Rate limits   │  │  • stations         │  │  • Simulated IoT Feed        │
│  • Session cache │  │  • slots            │  │                              │
│  • Idempotency   │  │  • bookings         │  └──────────────────────────────┘
│    keys          │  │  • users            │
│                  │  │  • payments         │  ┌──────────────────────────────┐
│  TTL Strategy:   │  │  • reviews          │  │   REALTIME LAYER             │
│  • Locks: 2 min  │  │  • notifications    │  │                              │
│  • Station: 10s  │  │                     │  │  Supabase Realtime           │
│  • Routes: 5 min │  │  PostGIS:           │  │  (Postgres CDC via           │
│                  │  │  • GIST Indexes     │  │   logical replication)       │
└──────────────────┘  │  • geography cols   │  │                              │
                      │  • radius queries   │  │  Channels:                   │
                      │                     │  │  • station:{id}:slots        │
                      │  Row Level Security │  │  • bookings:{user_id}        │
                      │  (RLS) Policies     │  │  • admin:all_stations        │
                      └─────────────────────┘  └──────────────────────────────┘
```

---

## 4. Component Breakdown

### 4.1 React Native Mobile App (Expo)

```
src/
├── app/                          # Expo Router (file-based routing)
│   ├── (auth)/
│   │   ├── login.tsx             # OTP phone entry
│   │   └── verify.tsx            # OTP verification
│   ├── (tabs)/
│   │   ├── map.tsx               # Main map view
│   │   ├── bookings.tsx          # My bookings
│   │   └── profile.tsx           # User profile
│   ├── station/
│   │   └── [id].tsx              # Station detail (dynamic route)
│   ├── booking/
│   │   ├── select-slot.tsx       # Slot selection
│   │   ├── payment.tsx           # Razorpay checkout
│   │   └── confirmation.tsx      # QR code confirmation
│   └── route-planner.tsx         # EV route planner
│
├── components/
│   ├── map/
│   │   ├── StationMarker.tsx     # Custom map pin with availability color
│   │   ├── StationBottomSheet.tsx# Draggable station list sheet
│   │   └── MapFilters.tsx        # Filter FAB + modal
│   ├── station/
│   │   ├── SlotGrid.tsx          # Visual slot availability grid
│   │   ├── ChargerCard.tsx       # Individual charger info
│   │   └── LiveBadge.tsx         # Animated "LIVE" indicator
│   ├── booking/
│   │   ├── TimeSlotPicker.tsx    # Time selection grid
│   │   ├── BookingQRCode.tsx     # QR code display
│   │   └── CancellationModal.tsx
│   └── common/
│       ├── LoadingSkeleton.tsx
│       └── ErrorBoundary.tsx
│
├── hooks/
│   ├── useStationRealtime.ts     # Supabase Realtime subscription
│   ├── useGeolocation.ts         # GPS with permission handling
│   ├── useBookingLock.ts         # Slot lock timer management
│   └── usePayment.ts             # Razorpay RN SDK wrapper
│
├── services/
│   ├── api.ts                    # Axios instance + interceptors
│   ├── supabase.ts               # Supabase client config
│   └── storage.ts                # SecureStore for tokens
│
├── store/
│   ├── authStore.ts              # Zustand auth state
│   ├── mapStore.ts               # Map viewport + filters state
│   └── bookingStore.ts           # Active booking state
│
└── utils/
    ├── geoUtils.ts               # Distance calculation helpers
    ├── chargerIcons.ts           # Charger type → icon mapping
    └── priceFormatter.ts         # ₹ formatting utilities
```

### 4.2 FastAPI Backend

```
backend/
├── app/
│   ├── main.py                   # App factory, middleware registration
│   ├── config.py                 # Pydantic Settings (env vars)
│   │
│   ├── api/
│   │   ├── v1/
│   │   │   ├── auth.py           # OTP send/verify, token refresh
│   │   │   ├── stations.py       # CRUD + nearby search
│   │   │   ├── slots.py          # Slot availability + locking
│   │   │   ├── bookings.py       # Create/read/cancel bookings
│   │   │   ├── payments.py       # Razorpay order + webhook
│   │   │   ├── routes.py         # EV route planner
│   │   │   ├── reviews.py        # Station ratings
│   │   │   ├── notifications.py  # Push notification triggers
│   │   │   └── admin/
│   │   │       ├── stations.py   # Admin station management
│   │   │       ├── analytics.py  # Usage + revenue analytics
│   │   │       └── users.py      # User management
│   │
│   ├── core/
│   │   ├── security.py           # JWT creation/verification
│   │   ├── dependencies.py       # FastAPI dependency injection
│   │   ├── exceptions.py         # Custom exception handlers
│   │   └── middleware.py         # Rate limiting, logging, CORS
│   │
│   ├── models/
│   │   ├── user.py               # SQLModel User
│   │   ├── station.py            # SQLModel Station + EVSE
│   │   ├── slot.py               # SQLModel Slot
│   │   ├── booking.py            # SQLModel Booking
│   │   └── payment.py            # SQLModel Payment
│   │
│   ├── schemas/
│   │   ├── station.py            # Pydantic request/response schemas
│   │   ├── booking.py
│   │   ├── payment.py
│   │   └── auth.py
│   │
│   ├── services/
│   │   ├── booking_service.py    # Slot locking + booking orchestration
│   │   ├── payment_service.py    # Razorpay integration
│   │   ├── geo_service.py        # PostGIS query builders
│   │   ├── route_service.py      # EV route calculation
│   │   ├── notification_service.py # Expo push
│   │   ├── iot_service.py        # IoT/OCPP status ingestion
│   │   └── analytics_service.py  # Dashboard aggregations
│   │
│   ├── db/
│   │   ├── session.py            # Async SQLAlchemy engine
│   │   ├── migrations/           # Alembic migrations
│   │   └── seed.py               # Bhopal station seed data
│   │
│   └── cache/
│       ├── redis_client.py       # Redis async client
│       └── lock_manager.py       # Distributed lock primitives
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── load/                     # Locust load test scripts
│
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

### 4.3 Admin Dashboard (Next.js)

```
admin/
├── app/
│   ├── dashboard/
│   │   ├── page.tsx              # KPI overview
│   │   ├── stations/
│   │   │   ├── page.tsx          # Station list + management
│   │   │   └── [id]/page.tsx     # Individual station editor
│   │   ├── bookings/page.tsx     # All bookings table
│   │   ├── analytics/page.tsx    # Charts + heatmap
│   │   └── users/page.tsx        # User management
│   └── api/                      # Next.js API routes (proxy to FastAPI)
│
├── components/
│   ├── LiveStationGrid.tsx       # Real-time slot status grid
│   ├── DemandHeatmap.tsx         # D3.js time × day heatmap
│   ├── RevenueChart.tsx          # Recharts revenue trend
│   └── BookingsTable.tsx         # TanStack Table with filters
```

---

## 5. Technology Stack — Justified

### 5.1 Frontend

| Technology | Version | Justification |
|---|---|---|
| React Native | 0.74+ | Cross-platform iOS + Android from single codebase. Zomato, Uber, Swiggy all use RN in production |
| Expo | SDK 51+ | Zero native build config. OTA updates. Expo Go for instant device testing |
| Expo Router | v3 | File-based routing — same mental model as Next.js App Router |
| React Native Maps | Latest | Google Maps SDK wrapper. Native performance for map interactions |
| Zustand | v4 | Lightweight state management. No Redux boilerplate. Supabase Realtime plays well with Zustand |
| TanStack Query | v5 | Server state, caching, background refetch. Replaces manual loading/error state |
| Supabase JS | v2 | Realtime subscriptions, auth client, direct DB queries for non-sensitive reads |

### 5.2 Backend

| Technology | Version | Justification |
|---|---|---|
| FastAPI | 0.111+ | Async-first. Auto OpenAPI docs. Pydantic validation. Python 3.12 perf gains |
| SQLAlchemy | 2.0 (Async) | Async ORM with full PostgreSQL + PostGIS support via GeoAlchemy2 |
| Alembic | Latest | Schema migration management. Version-controlled DB changes |
| Redis | 7.x | Distributed slot locks (SETNX + EXPIRE), rate limiting, response caching |
| Uvicorn + Gunicorn | Latest | Production ASGI server. Multi-worker process model |
| Pydantic | v2 | 5–10x faster validation vs v1. Request/response schema enforcement |

### 5.3 Database

| Technology | Version | Justification |
|---|---|---|
| Supabase | Latest | Managed PostgreSQL + built-in Realtime (CDC) + Auth + Storage + RLS policies |
| PostgreSQL | 15+ | ACID compliance for booking integrity. JSON support for flexible metadata |
| PostGIS | 3.4+ | Native geospatial — ST_DWithin for radius queries, ST_Distance for sorting by proximity. 100x faster than app-layer geo math |

### 5.4 Infrastructure

| Technology | Justification |
|---|---|
| Docker + Docker Compose | Reproducible environments. Single `docker-compose up` for full local stack |
| Railway | FastAPI deployment. Auto-deploys from GitHub. Free tier sufficient for hackathon |
| Vercel | Admin dashboard deployment. Edge network, zero config Next.js |
| Supabase Cloud | Managed DB + Realtime. Free tier: 500MB DB, 2GB bandwidth, 50k MAU |

---

## 6. Database Design (Supabase + PostgreSQL + PostGIS)

### 6.1 Schema Overview

```
┌──────────┐     ┌──────────────┐     ┌──────────┐     ┌──────────┐
│  users   │     │   stations   │     │  slots   │     │ bookings │
│          │     │              │     │          │     │          │
│ id (PK)  │────▶│ id (PK)      │────▶│ id (PK)  │◀────│ id (PK)  │
│ phone    │     │ name         │     │station_id│     │ user_id  │
│ name     │     │ network      │     │slot_num  │     │ slot_id  │
│ vehicle  │     │ location     │     │type      │     │ start_at │
│ role     │     │ (geography)  │     │status    │     │ end_at   │
│          │     │ address      │     │power_kw  │     │ status   │
└──────────┘     │ total_slots  │     │connector │     │ amount   │
                 │ is_active    │     │          │     │ qr_code  │
                 └──────────────┘     └──────────┘     └──────────┘
                                                              │
                                      ┌──────────┐           │
                                      │ payments │◀──────────┘
                                      │          │
                                      │ id (PK)  │
                                      │booking_id│
                                      │amount    │
                                      │status    │
                                      │razorpay_ │
                                      │order_id  │
                                      └──────────┘
```

### 6.2 Full DDL

```sql
-- ============================================================
-- EXTENSIONS
-- ============================================================
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm; -- For text search

-- ============================================================
-- ENUM TYPES
-- ============================================================
CREATE TYPE user_role AS ENUM ('user', 'fleet_manager', 'station_admin', 'super_admin');
CREATE TYPE charger_type AS ENUM ('AC_SLOW', 'AC_FAST', 'DC_FAST', 'CCS2', 'CHAdeMO', 'TYPE2', 'BHARAT_AC', 'BHARAT_DC');
CREATE TYPE slot_status AS ENUM ('AVAILABLE', 'BOOKED', 'IN_USE', 'OFFLINE', 'LOCKED');
CREATE TYPE booking_status AS ENUM ('PENDING_PAYMENT', 'CONFIRMED', 'ACTIVE', 'COMPLETED', 'CANCELLED', 'NO_SHOW', 'REFUNDED');
CREATE TYPE payment_status AS ENUM ('INITIATED', 'SUCCESS', 'FAILED', 'REFUNDED', 'PARTIALLY_REFUNDED');
CREATE TYPE network_operator AS ENUM ('TATA_POWER', 'CHARGE_ZONE', 'STATIQ', 'ATHER_GRID', 'BPCL_PULSE', 'EESL', 'INDEPENDENT');

-- ============================================================
-- USERS TABLE
-- ============================================================
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phone           VARCHAR(15) NOT NULL UNIQUE,
    name            VARCHAR(100),
    email           VARCHAR(255) UNIQUE,
    role            user_role NOT NULL DEFAULT 'user',
    vehicle_type    VARCHAR(50),               -- e.g. 'Tata Nexon EV', 'Ather 450X'
    preferred_connector charger_type,
    expo_push_token TEXT,                      -- For push notifications
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- STATIONS TABLE
-- ============================================================
CREATE TABLE stations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(200) NOT NULL,
    network         network_operator NOT NULL DEFAULT 'INDEPENDENT',
    
    -- PostGIS geography column — EPSG:4326 (WGS84)
    location        GEOGRAPHY(POINT, 4326) NOT NULL,
    
    -- Human-readable address
    address_line1   VARCHAR(255) NOT NULL,
    address_line2   VARCHAR(255),
    city            VARCHAR(100) NOT NULL,
    state           VARCHAR(100) NOT NULL,
    pincode         VARCHAR(10) NOT NULL,
    
    -- Operational metadata
    total_slots     INTEGER NOT NULL CHECK (total_slots > 0),
    available_slots INTEGER NOT NULL DEFAULT 0 CHECK (available_slots >= 0),
    operating_hours JSONB NOT NULL DEFAULT '{"open": "00:00", "close": "23:59", "days": [1,2,3,4,5,6,7]}',
    amenities       TEXT[],                    -- ['parking', 'wifi', 'restroom', 'food']
    
    -- Pricing
    price_per_unit  DECIMAL(8, 2),             -- ₹ per kWh
    price_per_hour  DECIMAL(8, 2),             -- ₹ per hour (for time-based billing)
    
    -- OCPP-ready fields
    ocpp_station_id VARCHAR(100),              -- OCPP ChargePointId
    firmware_version VARCHAR(50),
    
    -- Status
    is_active       BOOLEAN NOT NULL DEFAULT true,
    is_verified     BOOLEAN NOT NULL DEFAULT false,
    avg_rating      DECIMAL(3, 2) DEFAULT 0.0 CHECK (avg_rating BETWEEN 0 AND 5),
    total_reviews   INTEGER DEFAULT 0,
    
    -- Managed by
    admin_user_id   UUID REFERENCES users(id) ON DELETE SET NULL,
    
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- SLOTS TABLE (individual charger units within a station)
-- ============================================================
CREATE TABLE slots (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    station_id      UUID NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
    slot_number     INTEGER NOT NULL,          -- Display number (Slot #1, #2...)
    
    -- Charger specs
    charger_type    charger_type NOT NULL,
    power_kw        DECIMAL(5, 2) NOT NULL,    -- e.g., 7.2, 22.0, 50.0, 150.0
    connector_count INTEGER NOT NULL DEFAULT 1,
    
    -- OCPP mapping
    evse_id         VARCHAR(100),              -- OCPP EVSE identifier
    connector_id    INTEGER DEFAULT 1,
    
    -- Current state
    status          slot_status NOT NULL DEFAULT 'AVAILABLE',
    locked_until    TIMESTAMPTZ,               -- Slot lock expiry
    locked_by_user  UUID REFERENCES users(id),
    
    -- Hardware status
    last_heartbeat  TIMESTAMPTZ,               -- Last OCPP heartbeat
    fault_code      VARCHAR(50),               -- OCPP fault code if any
    
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE(station_id, slot_number)
);

-- ============================================================
-- BOOKINGS TABLE
-- ============================================================
CREATE TABLE bookings (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id),
    slot_id         UUID NOT NULL REFERENCES slots(id),
    station_id      UUID NOT NULL REFERENCES stations(id),
    
    -- Time window
    scheduled_start TIMESTAMPTZ NOT NULL,
    scheduled_end   TIMESTAMPTZ NOT NULL,
    actual_start    TIMESTAMPTZ,
    actual_end      TIMESTAMPTZ,
    
    -- Booking details
    status          booking_status NOT NULL DEFAULT 'PENDING_PAYMENT',
    qr_code         VARCHAR(255) UNIQUE NOT NULL DEFAULT encode(gen_random_bytes(16), 'hex'),
    
    -- Energy tracking
    energy_consumed_kwh DECIMAL(8, 3),         -- Filled post-session
    
    -- Financial
    amount_charged  DECIMAL(10, 2) NOT NULL,
    amount_refunded DECIMAL(10, 2) DEFAULT 0,
    
    -- Idempotency
    idempotency_key UUID NOT NULL UNIQUE,
    
    -- Metadata
    cancellation_reason TEXT,
    notes           TEXT,
    
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT no_overlapping_bookings EXCLUDE USING gist (
        slot_id WITH =,
        tstzrange(scheduled_start, scheduled_end, '[)') WITH &&
    ) WHERE (status NOT IN ('CANCELLED', 'REFUNDED', 'NO_SHOW'))
);

-- ============================================================
-- PAYMENTS TABLE
-- ============================================================
CREATE TABLE payments (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    booking_id          UUID NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
    user_id             UUID NOT NULL REFERENCES users(id),
    
    -- Razorpay identifiers
    razorpay_order_id   VARCHAR(100) NOT NULL UNIQUE,
    razorpay_payment_id VARCHAR(100) UNIQUE,
    razorpay_signature  VARCHAR(255),
    
    -- Financials
    amount              DECIMAL(10, 2) NOT NULL, -- in ₹
    currency            VARCHAR(3) NOT NULL DEFAULT 'INR',
    payment_method      VARCHAR(50),             -- 'upi', 'card', 'netbanking'
    upi_vpa             VARCHAR(100),            -- e.g., user@upi
    
    status              payment_status NOT NULL DEFAULT 'INITIATED',
    
    -- Webhook validation
    webhook_verified    BOOLEAN DEFAULT false,
    webhook_received_at TIMESTAMPTZ,
    
    -- Refund tracking
    refund_id           VARCHAR(100),
    refunded_at         TIMESTAMPTZ,
    
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- REVIEWS TABLE
-- ============================================================
CREATE TABLE reviews (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    station_id  UUID NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
    user_id     UUID NOT NULL REFERENCES users(id),
    booking_id  UUID REFERENCES bookings(id),   -- Only verified visitors can review
    rating      INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment     TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE(station_id, user_id, booking_id)     -- One review per visit
);

-- ============================================================
-- NOTIFICATIONS TABLE
-- ============================================================
CREATE TABLE notifications (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES users(id),
    type        VARCHAR(50) NOT NULL,           -- 'BOOKING_CONFIRMED', 'SLOT_REMINDER', etc.
    title       VARCHAR(200) NOT NULL,
    body        TEXT NOT NULL,
    data        JSONB,                          -- Deep link / action data
    is_read     BOOLEAN DEFAULT false,
    sent_at     TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- INDEXES
-- ============================================================

-- Geospatial index — critical for ST_DWithin radius queries
CREATE INDEX idx_stations_location ON stations USING GIST (location);

-- Station lookup
CREATE INDEX idx_stations_network ON stations (network);
CREATE INDEX idx_stations_city ON stations (city);
CREATE INDEX idx_stations_active ON stations (is_active) WHERE is_active = true;

-- Slot queries
CREATE INDEX idx_slots_station ON slots (station_id);
CREATE INDEX idx_slots_status ON slots (status);
CREATE INDEX idx_slots_locked_until ON slots (locked_until) WHERE locked_until IS NOT NULL;

-- Booking queries
CREATE INDEX idx_bookings_user ON bookings (user_id);
CREATE INDEX idx_bookings_slot ON bookings (slot_id);
CREATE INDEX idx_bookings_station ON bookings (station_id);
CREATE INDEX idx_bookings_status ON bookings (status);
CREATE INDEX idx_bookings_scheduled ON bookings (scheduled_start, scheduled_end);

-- Payment queries
CREATE INDEX idx_payments_booking ON payments (booking_id);
CREATE INDEX idx_payments_razorpay_order ON payments (razorpay_order_id);

-- Text search on station names
CREATE INDEX idx_stations_name_trgm ON stations USING gin (name gin_trgm_ops);

-- ============================================================
-- FUNCTIONS & TRIGGERS
-- ============================================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_stations_updated_at BEFORE UPDATE ON stations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_slots_updated_at BEFORE UPDATE ON slots
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_bookings_updated_at BEFORE UPDATE ON bookings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Auto-recalculate station available_slots count
CREATE OR REPLACE FUNCTION refresh_station_available_slots()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE stations
    SET available_slots = (
        SELECT COUNT(*) FROM slots
        WHERE station_id = COALESCE(NEW.station_id, OLD.station_id)
        AND status = 'AVAILABLE'
        AND is_active = true
    )
    WHERE id = COALESCE(NEW.station_id, OLD.station_id);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_refresh_available_slots
    AFTER INSERT OR UPDATE OR DELETE ON slots
    FOR EACH ROW EXECUTE FUNCTION refresh_station_available_slots();

-- Expired lock auto-release function (called by scheduled job)
CREATE OR REPLACE FUNCTION release_expired_locks()
RETURNS void AS $$
BEGIN
    UPDATE slots
    SET status = 'AVAILABLE', locked_until = NULL, locked_by_user = NULL
    WHERE status = 'LOCKED'
    AND locked_until < NOW();
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ============================================================

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE bookings ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;

-- Users can only read/update their own data
CREATE POLICY users_self_access ON users
    FOR ALL USING (auth.uid() = id);

-- Users can only see their own bookings
CREATE POLICY bookings_owner_access ON bookings
    FOR ALL USING (auth.uid() = user_id);

-- Super admins bypass RLS
CREATE POLICY admin_bypass ON bookings
    FOR ALL TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM users
            WHERE id = auth.uid() AND role IN ('station_admin', 'super_admin')
        )
    );
```

### 6.3 Key Design Decisions

| Decision | Rationale |
|---|---|
| `GEOGRAPHY` type for location | Uses spherical earth model — accurate distance calculations in India's lat/lng range without coordinate projection math |
| `EXCLUDE USING gist` constraint on bookings | Database-enforced overlap prevention — no two confirmed bookings can exist for the same slot in the same time window. This is the gold standard for reservation systems |
| `idempotency_key` on bookings | Prevents duplicate bookings on network retry. Client generates UUID v4, server rejects duplicate keys with 409 |
| Denormalized `available_slots` on stations | Avoids COUNT(*) on every map load. Trigger keeps it in sync. Read path is O(1) |
| `status NOT IN (...)` partial index | Overlap exclusion constraint only applies to active bookings — cancelled/refunded bookings don't block slot reuse |

---

## 7. API Design Specification

### 7.1 Base Configuration

```
Base URL:       https://api.evchargefinder.in/v1
Auth Header:    Authorization: Bearer <access_token>
Content-Type:   application/json
Idempotency:    Idempotency-Key: <uuid-v4>  (required for POST /bookings, /payments)
Rate Limits:    100 req/min (authenticated), 20 req/min (unauthenticated)
```

### 7.2 Authentication Endpoints

```
POST   /auth/otp/send
POST   /auth/otp/verify
POST   /auth/token/refresh
DELETE /auth/logout
GET    /auth/me
PATCH  /auth/me
```

**POST /auth/otp/send**
```json
// Request
{ "phone": "+919876543210" }

// Response 200
{ "message": "OTP sent", "expires_in": 300 }

// Response 429
{ "error": "RATE_LIMITED", "retry_after": 60 }
```

**POST /auth/otp/verify**
```json
// Request
{ "phone": "+919876543210", "otp": "482910" }

// Response 200
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "Bearer",
  "expires_in": 900,
  "user": {
    "id": "uuid",
    "phone": "+919876543210",
    "name": null,
    "role": "user",
    "is_new_user": true
  }
}
```

### 7.3 Station Endpoints

```
GET    /stations/nearby          # Radius search (primary map load)
GET    /stations/:id             # Station detail
GET    /stations/:id/slots       # All slots with live status
POST   /stations                 # Admin: create station
PATCH  /stations/:id             # Admin: update station
DELETE /stations/:id             # Admin: deactivate
```

**GET /stations/nearby** — The most performance-critical endpoint
```
Query Params:
  lat         float   required    User latitude
  lng         float   required    User longitude
  radius_km   float   default=10  Search radius
  charger_type string optional    Filter by charger type
  available_only bool default=false
  limit       int     default=20  Max results
  offset      int     default=0

Response 200:
{
  "stations": [
    {
      "id": "uuid",
      "name": "Tata Power EZ Charge — DB Mall",
      "network": "TATA_POWER",
      "distance_km": 1.24,
      "location": { "lat": 23.2599, "lng": 77.4126 },
      "address": "DB Mall, MP Nagar, Bhopal",
      "available_slots": 3,
      "total_slots": 8,
      "charger_types": ["CCS2", "TYPE2"],
      "max_power_kw": 50.0,
      "price_per_unit": 18.00,
      "avg_rating": 4.3,
      "is_active": true,
      "estimated_wait_minutes": 0
    }
  ],
  "total": 12,
  "radius_km": 10
}
```

**Internal PostGIS Query:**
```sql
SELECT
    s.id,
    s.name,
    s.network,
    ST_Distance(s.location, ST_MakePoint(:lng, :lat)::geography) / 1000 AS distance_km,
    ST_Y(s.location::geometry) AS lat,
    ST_X(s.location::geometry) AS lng,
    s.available_slots,
    s.total_slots,
    s.price_per_unit,
    s.avg_rating,
    ARRAY_AGG(DISTINCT sl.charger_type) AS charger_types,
    MAX(sl.power_kw) AS max_power_kw
FROM stations s
LEFT JOIN slots sl ON sl.station_id = s.id AND sl.is_active = true
WHERE
    s.is_active = true
    AND ST_DWithin(
        s.location,
        ST_MakePoint(:lng, :lat)::geography,
        :radius_km * 1000  -- Convert km to meters
    )
GROUP BY s.id
ORDER BY distance_km ASC
LIMIT :limit OFFSET :offset;
```

### 7.4 Booking Endpoints

```
POST   /bookings                 # Create booking (initiate payment)
GET    /bookings                 # User's booking history
GET    /bookings/:id             # Booking detail + QR
PATCH  /bookings/:id/cancel      # Cancel booking
POST   /bookings/:id/checkin     # QR scan check-in
```

**POST /bookings**
```json
// Request Headers
// Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000

// Request Body
{
  "slot_id": "uuid",
  "scheduled_start": "2026-05-13T14:00:00+05:30",
  "scheduled_end": "2026-05-13T14:45:00+05:30"
}

// Response 201 — Booking created, payment pending
{
  "booking_id": "uuid",
  "razorpay_order_id": "order_xyz123",
  "amount": 180.00,
  "currency": "INR",
  "key_id": "rzp_test_xxx",
  "lock_expires_at": "2026-05-13T12:02:00Z",
  "status": "PENDING_PAYMENT"
}

// Response 409 — Slot unavailable or overlap
{
  "error": "SLOT_UNAVAILABLE",
  "message": "This slot is already booked for the selected time window"
}

// Response 409 — Duplicate idempotency key
{
  "error": "DUPLICATE_REQUEST",
  "existing_booking_id": "uuid"
}
```

### 7.5 Payment Endpoints

```
POST   /payments/verify          # Client-side signature verification
POST   /payments/webhook         # Razorpay server webhook (no auth)
GET    /payments/:booking_id     # Payment receipt
POST   /payments/:booking_id/refund  # Admin: manual refund trigger
```

**POST /payments/webhook** (Razorpay → Server, no JWT auth)
```json
// Razorpay sends:
{
  "event": "payment.captured",
  "payload": {
    "payment": {
      "entity": {
        "id": "pay_xxx",
        "order_id": "order_xxx",
        "amount": 18000,
        "status": "captured",
        "method": "upi"
      }
    }
  }
}
```

### 7.6 Route Planner Endpoint

```
POST   /routes/ev-plan
```

```json
// Request
{
  "origin": { "lat": 23.2599, "lng": 77.4126 },
  "destination": { "lat": 22.7196, "lng": 75.8577 },
  "vehicle_range_km": 300,
  "current_battery_percent": 65,
  "preferred_charger_type": "CCS2",
  "departure_time": "2026-05-13T09:00:00+05:30"
}

// Response
{
  "route": {
    "total_distance_km": 193,
    "estimated_duration_min": 195,
    "charging_stops": [
      {
        "station_id": "uuid",
        "station_name": "ChargeZone Hoshangabad",
        "distance_from_origin_km": 78,
        "arrival_battery_percent": 28,
        "recommended_charge_to_percent": 80,
        "estimated_charge_duration_min": 35,
        "available_slots_at_arrival": 2,
        "charger_type": "DC_FAST",
        "price_per_unit": 15.50
      }
    ],
    "polyline": "encoded_google_polyline_string"
  }
}
```

---

## 8. Real-Time Architecture (WebSocket + Supabase Realtime)

### 8.1 Architecture Overview

```
Slot Status Change (DB)
        │
        ▼
Supabase Postgres CDC
(Logical Replication)
        │
        ▼
Supabase Realtime Server
(Phoenix Channels)
        │
        ▼ WebSocket
React Native Client ──▶ useStationRealtime() hook
        │
        ▼
Update Zustand store ──▶ Re-render SlotGrid component
```

### 8.2 Supabase Realtime Channels

```typescript
// hooks/useStationRealtime.ts

import { useEffect } from 'react'
import { supabase } from '@/services/supabase'
import { useMapStore } from '@/store/mapStore'

export function useStationRealtime(stationId: string) {
  const updateSlotStatus = useMapStore(s => s.updateSlotStatus)
  const updateAvailableCount = useMapStore(s => s.updateAvailableCount)

  useEffect(() => {
    // Channel 1: Individual slot status changes
    const slotChannel = supabase
      .channel(`station:${stationId}:slots`)
      .on(
        'postgres_changes',
        {
          event: 'UPDATE',
          schema: 'public',
          table: 'slots',
          filter: `station_id=eq.${stationId}`
        },
        (payload) => {
          updateSlotStatus(payload.new.id, payload.new.status)
        }
      )
      .subscribe()

    // Channel 2: Station available_slots count (for map pins)
    const stationChannel = supabase
      .channel(`station:${stationId}:count`)
      .on(
        'postgres_changes',
        {
          event: 'UPDATE',
          schema: 'public',
          table: 'stations',
          filter: `id=eq.${stationId}`
        },
        (payload) => {
          updateAvailableCount(stationId, payload.new.available_slots)
        }
      )
      .subscribe()

    return () => {
      supabase.removeChannel(slotChannel)
      supabase.removeChannel(stationChannel)
    }
  }, [stationId])
}
```

### 8.3 Fallback Strategy

If WebSocket connection drops (common on Indian mobile networks):

```
WebSocket Connected → Normal Realtime updates (5s latency)
        │
Connection Drop Detected
        │
        ▼
Polling Fallback: GET /stations/:id/slots every 15 seconds
        │
WebSocket Reconnected
        │
        ▼
Resume Realtime, Stop Polling
```

---

## 9. Slot Booking & Concurrency Control

This is the most architecturally critical component. A race condition here means two users booking the same slot simultaneously — unacceptable.

### 9.1 Three-Phase Booking Flow

```
Phase 1: LOCK (2 minutes)
─────────────────────────
User selects slot → API acquires Redis distributed lock + sets slot status to LOCKED
→ Slot is invisible to other users for 2 minutes
→ If payment not completed in 2 min → auto-release

Phase 2: PAYMENT (within lock window)
──────────────────────────────────────
Razorpay order created → Client renders UPI/card sheet
→ User completes payment → Client calls /payments/verify
→ Server verifies Razorpay signature (HMAC-SHA256)
→ Server awaits webhook confirmation (dual validation)

Phase 3: CONFIRM
─────────────────
Both verify + webhook received → Booking status → CONFIRMED
→ Slot status → BOOKED
→ Redis lock released (no longer needed — DB booking record is the truth)
→ Push notification sent
→ QR code delivered
```

### 9.2 Distributed Lock Implementation

```python
# cache/lock_manager.py

import asyncio
import uuid
from datetime import datetime, timedelta
from app.cache.redis_client import redis

SLOT_LOCK_TTL = 120  # 2 minutes in seconds

async def acquire_slot_lock(slot_id: str, user_id: str) -> tuple[bool, str]:
    """
    Acquire a distributed lock on a slot using Redis SETNX.
    Returns (success, lock_token).
    """
    lock_key = f"slot_lock:{slot_id}"
    lock_token = str(uuid.uuid4())
    
    # SET key value NX EX 120
    # NX = Only set if not exists (atomic check-and-set)
    # EX = Expire in 120 seconds
    acquired = await redis.set(
        lock_key,
        f"{user_id}:{lock_token}",
        nx=True,
        ex=SLOT_LOCK_TTL
    )
    
    if acquired:
        # Update slot status in DB
        await update_slot_status(slot_id, 'LOCKED', user_id)
        return True, lock_token
    
    return False, ""

async def release_slot_lock(slot_id: str, lock_token: str) -> bool:
    """
    Release lock using Lua script for atomic check-and-delete.
    Prevents releasing another user's lock.
    """
    lua_script = """
    local key = KEYS[1]
    local token = ARGV[1]
    local current = redis.call('GET', key)
    if current and string.find(current, token) then
        return redis.call('DEL', key)
    end
    return 0
    """
    result = await redis.eval(lua_script, 1, f"slot_lock:{slot_id}", lock_token)
    
    if result:
        await update_slot_status(slot_id, 'AVAILABLE', None)
    
    return bool(result)

async def extend_slot_lock(slot_id: str, lock_token: str) -> bool:
    """Extend lock by additional 60 seconds if payment is in progress."""
    lock_key = f"slot_lock:{slot_id}"
    current = await redis.get(lock_key)
    
    if current and lock_token in current.decode():
        await redis.expire(lock_key, SLOT_LOCK_TTL)
        return True
    
    return False
```

### 9.3 Database-Level Safety Net

Even if Redis fails, the PostgreSQL `EXCLUDE USING gist` constraint is the ultimate safeguard:

```sql
-- This constraint makes double-booking physically impossible at the DB level
CONSTRAINT no_overlapping_bookings EXCLUDE USING gist (
    slot_id WITH =,
    tstzrange(scheduled_start, scheduled_end, '[)') WITH &&
) WHERE (status NOT IN ('CANCELLED', 'REFUNDED', 'NO_SHOW'))
```

If two concurrent transactions try to insert overlapping bookings for the same slot, PostgreSQL will raise a `23P01 exclusion_violation` error on the second one. The API layer catches this and returns a `409 SLOT_UNAVAILABLE`.

**Defense in depth:** Redis lock (fast path) + PostgreSQL constraint (safety net) = zero double bookings.

---

## 10. Authentication & Authorization

### 10.1 Token Architecture

```
Access Token:   JWT, 15-minute expiry, signed with RS256
Refresh Token:  JWT, 7-day expiry, stored in SecureStore (Expo)
OTP:            6-digit, 5-minute expiry, bcrypt-hashed in Redis
```

### 10.2 JWT Payload

```json
{
  "sub": "user-uuid",
  "phone": "+919876543210",
  "role": "user",
  "iat": 1746000000,
  "exp": 1746000900,
  "jti": "unique-jwt-id"   // For token revocation
}
```

### 10.3 RBAC Matrix

| Endpoint Group | `user` | `fleet_manager` | `station_admin` | `super_admin` |
|---|---|---|---|---|
| GET /stations/* | ✅ | ✅ | ✅ | ✅ |
| POST /bookings | ✅ | ✅ | ✅ | ✅ |
| POST /bookings (bulk) | ❌ | ✅ | ❌ | ✅ |
| PATCH /stations/:id | ❌ | ❌ | ✅ (own) | ✅ |
| GET /admin/analytics | ❌ | ❌ | ✅ (own) | ✅ |
| DELETE /users/:id | ❌ | ❌ | ❌ | ✅ |

### 10.4 OTP Flow

```
Client                     FastAPI                    Redis
  │                            │                         │
  │── POST /auth/otp/send ────▶│                         │
  │   { phone }                │── Generate OTP ────────▶│
  │                            │   SET otp:{phone}       │
  │                            │   bcrypt(otp), EX=300   │
  │◀── 200 OK ─────────────────│                         │
  │                            │                         │
  │── POST /auth/otp/verify ──▶│                         │
  │   { phone, otp }           │── GET otp:{phone} ─────▶│
  │                            │◀─ bcrypt_hash ──────────│
  │                            │── bcrypt.verify()        │
  │                            │── DELETE otp:{phone} ──▶│
  │                            │── Upsert user in DB      │
  │◀── 200 { tokens, user } ───│                         │
```

---

## 11. Payment Architecture (Razorpay)

### 11.1 End-to-End Payment Flow

```
Client App                 FastAPI Backend              Razorpay
    │                            │                         │
    │── POST /bookings ─────────▶│                         │
    │   (slot_id, time)          │── Acquire slot lock     │
    │                            │── POST /orders ────────▶│
    │                            │◀── { order_id, amount } │
    │◀── 201 { order_id, key } ──│                         │
    │                            │                         │
    │ [Razorpay SDK opens]        │                         │
    │── User pays via UPI ───────────────────────────────▶│
    │◀── payment_id, signature ──────────────────────────│
    │                            │                         │
    │── POST /payments/verify ──▶│                         │
    │   { order_id,              │── Verify HMAC-SHA256    │
    │     payment_id,            │   signature             │
    │     signature }            │── Mark payment          │
    │                            │   webhook_pending=true  │
    │◀── 200 { status: pending} ─│                         │
    │                            │                         │
    │                     [Razorpay Webhook]                │
    │                            │◀── payment.captured ───│
    │                            │── Verify webhook sig    │
    │                            │── UPDATE booking        │
    │                            │   status=CONFIRMED      │
    │                            │── UPDATE slot           │
    │                            │   status=BOOKED         │
    │                            │── Send push notification│
    │                            │── Release Redis lock    │
    │◀── Push: "Booking confirmed"│                        │
```

### 11.2 Signature Verification

```python
# services/payment_service.py

import hmac
import hashlib

def verify_razorpay_signature(
    order_id: str,
    payment_id: str,
    signature: str,
    secret: str
) -> bool:
    """
    Razorpay signature = HMAC-SHA256(order_id + "|" + payment_id, secret)
    """
    message = f"{order_id}|{payment_id}"
    expected = hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)

def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify Razorpay webhook payload signature."""
    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
```

---

## 12. Geospatial Query Design

### 12.1 Proximity Search Complexity Analysis

| Approach | Query Type | Performance at 10k stations | Notes |
|---|---|---|---|
| App-layer Haversine | Calculate distance for all rows | O(n) — full table scan | Never do this |
| PostGIS ST_Distance (no index) | Sequential scan + distance calc | O(n) | Still bad |
| **PostGIS ST_DWithin (GIST index)** | **Index scan + spatial filter** | **O(log n) ~1-3ms** | **Our approach** |

### 12.2 The GIST Index in Action

```sql
-- This query is what runs on every map load.
-- With GIST index on location, PostgreSQL uses a bounding box filter
-- before the exact spherical distance calculation.
-- At 10,000 stations, this runs in ~2ms.

EXPLAIN ANALYZE
SELECT id, name, ST_Distance(location, ST_MakePoint(77.4126, 23.2599)::geography) / 1000 AS dist_km
FROM stations
WHERE ST_DWithin(
    location,
    ST_MakePoint(77.4126, 23.2599)::geography,
    10000  -- 10km in meters
)
ORDER BY dist_km ASC
LIMIT 20;

-- Expected plan:
-- Index Scan using idx_stations_location on stations
-- (cost=0.28..8.41 rows=5 width=32) (actual time=0.124..1.834 ms)
```

---

## 13. Notification Architecture

### 13.1 Notification Types & Triggers

| Event | Trigger | Channel | Timing |
|---|---|---|---|
| `BOOKING_CONFIRMED` | Payment webhook received | Push + In-app | Immediate |
| `SLOT_REMINDER` | Cron job | Push | 15 min before slot |
| `BOOKING_CANCELLED` | Cancel API called | Push + In-app | Immediate |
| `REFUND_INITIATED` | Refund API called | Push + In-app | Immediate |
| `SLOT_AVAILABLE` | Slot status → AVAILABLE | Push | Immediate (if user subscribed) |
| `CHARGING_COMPLETE` | IoT session end event | Push | Immediate |

### 13.2 Expo Push Implementation

```python
# services/notification_service.py

import httpx
from app.models.user import User

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"

async def send_push(user: User, title: str, body: str, data: dict = None):
    if not user.expo_push_token:
        return

    async with httpx.AsyncClient() as client:
        await client.post(EXPO_PUSH_URL, json={
            "to": user.expo_push_token,
            "title": title,
            "body": body,
            "data": data or {},
            "sound": "default",
            "priority": "high",
            "channelId": "bookings"  # Android notification channel
        })

async def send_booking_confirmed(user: User, booking_id: str, station_name: str):
    await send_push(
        user,
        title="✅ Slot Confirmed!",
        body=f"Your slot at {station_name} is confirmed. Tap to view QR code.",
        data={"screen": "booking", "booking_id": booking_id}
    )

async def send_slot_reminder(user: User, booking_id: str, station_name: str, minutes: int):
    await send_push(
        user,
        title=f"⚡ Charging in {minutes} mins",
        body=f"Your slot at {station_name} starts in {minutes} minutes.",
        data={"screen": "booking", "booking_id": booking_id}
    )
```

---

## 14. AI Demand Prediction Module

### 14.1 Architecture

```
Historical Bookings Data (PostgreSQL)
            │
            ▼
Feature Engineering
• Hour of day (0–23)
• Day of week (0–6)
• Station ID
• Network operator
• City / Zone
• Weather proxy (weekday peak vs weekend leisure)
            │
            ▼
Model: Gradient Boosted Trees (XGBoost / LightGBM)
Target: booking_count for next 1-hour window
            │
            ▼
Predictions stored in Redis (TTL: 1 hour)
            │
            ▼
API: GET /stations/:id/demand-forecast
     Returns: { predicted_bookings: int, confidence: float, peak_hours: [int] }
            │
            ▼
Admin Dashboard: Heatmap visualization (D3.js)
```

### 14.2 Training Query

```sql
-- Feature extraction for model training
SELECT
    s.id AS station_id,
    s.network,
    s.city,
    EXTRACT(HOUR FROM b.scheduled_start AT TIME ZONE 'Asia/Kolkata') AS hour_of_day,
    EXTRACT(DOW FROM b.scheduled_start AT TIME ZONE 'Asia/Kolkata') AS day_of_week,
    COUNT(*) AS booking_count
FROM bookings b
JOIN stations s ON s.id = b.station_id
WHERE b.status IN ('CONFIRMED', 'COMPLETED', 'ACTIVE')
AND b.created_at > NOW() - INTERVAL '90 days'
GROUP BY s.id, s.network, s.city, hour_of_day, day_of_week
ORDER BY booking_count DESC;
```

### 14.3 Dynamic Pricing Formula

```
base_price = station.price_per_unit (₹/kWh)

demand_multiplier = 
    IF predicted_demand_percent > 80%  → 1.3x  (peak surge)
    IF predicted_demand_percent > 60%  → 1.15x (moderate)
    IF predicted_demand_percent < 30%  → 0.85x (off-peak discount)
    ELSE                               → 1.0x  (standard)

final_price = base_price × demand_multiplier
```

---

## 15. Admin Dashboard Architecture

### 15.1 Key Metrics — SQL Backing Queries

**Daily Revenue:**
```sql
SELECT
    DATE(b.created_at AT TIME ZONE 'Asia/Kolkata') AS date,
    SUM(p.amount) AS revenue,
    COUNT(b.id) AS total_bookings
FROM bookings b
JOIN payments p ON p.booking_id = b.id
WHERE p.status = 'SUCCESS'
AND b.created_at > NOW() - INTERVAL '30 days'
GROUP BY date
ORDER BY date DESC;
```

**Station Utilization Rate:**
```sql
SELECT
    s.name,
    COUNT(b.id) AS total_bookings,
    SUM(EXTRACT(EPOCH FROM (b.scheduled_end - b.scheduled_start)) / 3600) AS total_hours_booked,
    (s.total_slots * 24) AS available_slot_hours_per_day,
    ROUND(
        SUM(EXTRACT(EPOCH FROM (b.scheduled_end - b.scheduled_start)) / 3600) /
        (s.total_slots * 24) * 100, 2
    ) AS utilization_percent
FROM stations s
LEFT JOIN bookings b ON b.station_id = s.id
    AND b.status IN ('CONFIRMED', 'COMPLETED')
    AND b.scheduled_start::date = CURRENT_DATE
WHERE s.admin_user_id = :admin_id
GROUP BY s.id, s.name, s.total_slots;
```

---

## 16. Caching Strategy

### 16.1 Cache Layer Design

| Data | Cache Key Pattern | TTL | Invalidation |
|---|---|---|---|
| Station list (by area) | `stations:nearby:{lat_rounded}:{lng_rounded}:{radius}` | 10 seconds | On any slot status change |
| Station detail | `station:detail:{station_id}` | 30 seconds | On station UPDATE |
| Route calculation | `route:{origin_hash}:{dest_hash}` | 5 minutes | None (time-insensitive) |
| User session | `session:{user_id}` | 15 minutes | On logout |
| Idempotency keys | `idem:{key}` | 24 hours | Never (append-only) |
| OTP | `otp:{phone}` | 5 minutes | On verify/consume |
| Slot locks | `slot_lock:{slot_id}` | 120 seconds | On lock release |
| Demand forecast | `demand:{station_id}:{hour}:{dow}` | 1 hour | On model retrain |

### 16.2 Cache-Aside Pattern (Station Nearby)

```python
async def get_nearby_stations(lat: float, lng: float, radius_km: float):
    # Round coordinates to ~100m precision to maximize cache hits
    cache_key = f"stations:nearby:{round(lat, 3)}:{round(lng, 3)}:{radius_km}"
    
    # 1. Check cache
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # 2. Query DB
    stations = await db.execute(NEARBY_STATIONS_QUERY, lat=lat, lng=lng, radius_km=radius_km)
    
    # 3. Write to cache
    await redis.setex(cache_key, 10, json.dumps(stations))
    
    return stations
```

---

## 17. Security Architecture

### 17.1 Threat Model

| Threat | Attack Vector | Mitigation |
|---|---|---|
| Double booking | Concurrent POST /bookings | Redis SETNX lock + PostgreSQL EXCLUDE constraint |
| Payment tampering | Modified amount in client | Amount always sourced from DB Razorpay order, never client |
| Webhook spoofing | Fake Razorpay webhook | HMAC-SHA256 signature verification on raw body |
| OTP brute force | 6-digit OTP guessing | Max 5 attempts, 10-min lockout, bcrypt hashing |
| JWT theft | Token interception | 15-min access token TTL, secure storage (Expo SecureStore) |
| SQL injection | Malformed query params | SQLAlchemy parameterized queries only, no raw string concat |
| Rate abuse | API flooding | Redis sliding window rate limiter (100 req/min per user) |
| IDOR | Accessing other users' bookings | RLS policies + JWT sub claim validation in every query |
| Mass assignment | Extra fields in request body | Strict Pydantic schema validation, no `**kwargs` to ORM |

### 17.2 Payment Security Rules (Non-Negotiable)

1. **Never store** raw card numbers, CVV, or full UPI VPA server-side
2. **Never trust** client-supplied amount — always re-fetch from Razorpay order
3. **Always verify** both client-side signature AND webhook before confirming booking
4. **Webhook endpoint** is the only unauthenticated endpoint — validated by payload signature

---

## 18. Observability & Monitoring

### 18.1 Logging Schema (Structured JSON)

```json
{
  "timestamp": "2026-05-13T08:32:11.421Z",
  "level": "INFO",
  "service": "booking-service",
  "trace_id": "abc123",
  "user_id": "uuid",
  "method": "POST",
  "path": "/v1/bookings",
  "status_code": 201,
  "duration_ms": 143,
  "slot_id": "uuid",
  "booking_id": "uuid",
  "message": "Booking created successfully"
}
```

### 18.2 Key Metrics to Track

| Metric | Alert Threshold |
|---|---|
| API p95 latency | > 500ms |
| Booking success rate | < 95% |
| Payment success rate | < 98% |
| Slot lock contention rate | > 10% of lock attempts |
| WebSocket connection drops | > 5% of active sessions |
| DB connection pool exhaustion | > 80% utilized |
| Redis memory usage | > 70% |

---

## 19. Deployment Architecture

### 19.1 Docker Compose (Local Dev)

```yaml
# docker-compose.yml
version: '3.9'

services:
  api:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=${SUPABASE_DB_URL}
      - REDIS_URL=redis://redis:6379
      - RAZORPAY_KEY_ID=${RAZORPAY_KEY_ID}
      - RAZORPAY_KEY_SECRET=${RAZORPAY_KEY_SECRET}
      - JWT_PRIVATE_KEY=${JWT_PRIVATE_KEY}
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_SERVICE_KEY=${SUPABASE_SERVICE_KEY}
    depends_on:
      - redis
    command: gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes

  admin:
    build: ./admin
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://api:8000

volumes:
  redis_data:
```

### 19.2 Production Topology

```
Internet
    │
    ▼
Cloudflare (DDoS protection + CDN)
    │
    ├──▶ Railway (FastAPI + Gunicorn, 2 replicas)
    │         └──▶ Supabase Cloud (PostgreSQL + Realtime)
    │         └──▶ Redis Cloud (Upstash — serverless Redis)
    │
    ├──▶ Vercel (Admin Dashboard — Next.js)
    │
    └──▶ Expo EAS (Mobile App builds — iOS + Android)
```

---

## 20. Scalability & Failure Analysis

### 20.1 Bottleneck Analysis

| Component | Bottleneck | Solution |
|---|---|---|
| Station nearby query | High read volume on map load | Redis cache (10s TTL) + read replica |
| Slot booking | Concurrent lock contention | Redis SETNX (serializes at lock level, not DB level) |
| Realtime WebSocket | Connection count per Supabase instance | Supabase scales channel connections — free tier: 200 concurrent |
| Payment webhook | Bursty webhook delivery | Idempotent handler + async DB write |
| Route calculation | Google Maps API rate limits | Cache routes (5-min TTL), batch waypoint requests |

### 20.2 Failure Mode Analysis

| Failure | Impact | Recovery |
|---|---|---|
| Redis down | Slot locking falls back to DB-level constraint | DB constraint catches duplicates, slight latency increase |
| Supabase Realtime down | Live availability stops updating | Polling fallback (15s) activates automatically |
| Razorpay webhook delayed | Booking stuck in PENDING_PAYMENT | Scheduled job reconciles pending bookings every 5 min via Razorpay fetch API |
| Google Maps API quota | Map fails to load | MapmyIndia fallback |
| FastAPI instance crash | Railway auto-restarts container | 2-replica setup ensures <5s downtime |

### 20.3 Scalability Numbers

| Scale Tier | Load | Architecture Change Required |
|---|---|---|
| MVP / Hackathon | 10 concurrent users, 30 stations | Current design — zero changes |
| City Launch (Bhopal) | 500 DAU, 100 stations | Add Redis read replica, increase Supabase plan |
| State Launch (MP) | 10k DAU, 1000 stations | Add PostGIS read replica, introduce message queue (Redis Pub/Sub) for notifications |
| National Scale | 1M DAU, 50k stations | Separate microservices, Kafka for event streaming, ElasticSearch for station search |

---

## 21. Data Flow Diagrams

### 21.1 Slot Booking — Complete Data Flow

```
User Action: "Book Slot #3 at DB Mall Tata Power, 2PM–2:45PM"

Step 1  Client validates form locally (date, time, slot selection)
Step 2  Client generates idempotency_key (UUID v4)
Step 3  POST /v1/bookings { slot_id, start, end, idempotency_key }
Step 4  FastAPI: Check idempotency key in Redis → not found, proceed
Step 5  FastAPI: BEGIN TRANSACTION
Step 6  FastAPI: Verify slot is AVAILABLE in DB (SELECT FOR UPDATE)
Step 7  FastAPI: Call acquire_slot_lock(slot_id, user_id) → Redis SETNX
Step 8  FastAPI: UPDATE slots SET status='LOCKED', locked_until=NOW()+2min
Step 9  FastAPI: Create Razorpay order via API → get order_id
Step 10 FastAPI: INSERT INTO bookings (status='PENDING_PAYMENT')
Step 11 FastAPI: Store idempotency_key in Redis (TTL 24h)
Step 12 FastAPI: COMMIT TRANSACTION
Step 13 Response 201 → { booking_id, razorpay_order_id, amount, lock_expires_at }
Step 14 Client: Razorpay SDK opens UPI sheet
Step 15 User: Pays via UPI
Step 16 Client: Receives { payment_id, signature } from Razorpay SDK
Step 17 Client: POST /v1/payments/verify { order_id, payment_id, signature }
Step 18 FastAPI: Verify HMAC-SHA256 signature → valid
Step 19 FastAPI: UPDATE payments SET status='PENDING_WEBHOOK'
Step 20 [Asynchronous] Razorpay sends webhook POST /v1/payments/webhook
Step 21 FastAPI: Verify webhook signature → valid
Step 22 FastAPI: BEGIN TRANSACTION
Step 23 FastAPI: UPDATE bookings SET status='CONFIRMED'
Step 24 FastAPI: UPDATE slots SET status='BOOKED', locked_until=NULL
Step 25 FastAPI: UPDATE payments SET status='SUCCESS', webhook_verified=true
Step 26 FastAPI: COMMIT TRANSACTION
Step 27 FastAPI: release_slot_lock(slot_id) → Redis DEL
Step 28 FastAPI: Supabase Realtime fires → all clients viewing station see slot go red
Step 29 FastAPI: send_push(user, "✅ Slot Confirmed!", booking_id)
Step 30 Client: Push notification received → user opens QR code screen
```

---

## 22. OCPP Integration Layer (Future-Ready)

The MVP simulates IoT data. When real OCPP hardware is connected, the integration point is isolated to a single service module.

### 22.1 OCPP Message Mapping

| OCPP Message | Our Domain Event | Action |
|---|---|---|
| `BootNotification` | Station comes online | UPDATE stations SET is_active=true, last_heartbeat=NOW() |
| `StatusNotification` | Slot status change | UPDATE slots SET status=map_ocpp_status(payload.status) |
| `StartTransaction` | Charging session begins | UPDATE bookings SET status='ACTIVE', actual_start=NOW() |
| `StopTransaction` | Charging session ends | UPDATE bookings SET status='COMPLETED', energy_consumed_kwh=payload.meterStop |
| `Heartbeat` | Station alive | UPDATE stations SET last_heartbeat=NOW() |

### 22.2 OCPP Status Mapping

```python
OCPP_TO_SLOT_STATUS = {
    "Available":   "AVAILABLE",
    "Preparing":   "IN_USE",      # EV plugged, not charging yet
    "Charging":    "IN_USE",
    "SuspendedEV": "IN_USE",
    "Finishing":   "IN_USE",
    "Reserved":    "BOOKED",
    "Unavailable": "OFFLINE",
    "Faulted":     "OFFLINE",
}
```

This mapping is the **only change needed** to go from simulated IoT to real OCPP hardware. The rest of the system is unchanged.

---

*Document End — EVChargeFinder HLD + TRD v1.0*

*Next Documents:*
- *API_SPEC.md — Full OpenAPI 3.0 specification*
- *DB_MIGRATIONS.md — Alembic migration files*
- *DEPLOYMENT.md — Railway + Vercel + Supabase setup guide*
