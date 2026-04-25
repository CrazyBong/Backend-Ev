# Product Requirements Document (PRD)
## EVChargeFinder — Intelligent EV Charging Station Locator & Slot Booking System

---

| Field | Details |
|---|---|
| **Document Version** | v1.0 |
| **Status** | Draft |
| **Created By** | Shubhranshu Das (Reesh) |
| **Date** | April 2026 |
| **Hackathon** | BGI Hackathon — Vision 2047 Viksit Bharat (Problem ID: BT2P2) |
| **Event Date** | 13th & 14th May 2026, Bhopal |

---

## Table of Contents

1. [Overview / Background](#1-overview--background)
2. [Goals & Objectives](#2-goals--objectives)
3. [Scope](#3-scope)
4. [User Personas / Target Audience](#4-user-personas--target-audience)
5. [Functional Requirements](#5-functional-requirements)
6. [Non-Functional Requirements](#6-non-functional-requirements)
7. [User Stories / Use Cases](#7-user-stories--use-cases)
8. [Wireframes / Mockups](#8-wireframes--mockups)
9. [Acceptance Criteria](#9-acceptance-criteria)
10. [Dependencies](#10-dependencies)
11. [Risks & Assumptions](#11-risks--assumptions)
12. [Timeline / Milestones](#12-timeline--milestones)
13. [Unique Selling Points (USP)](#13-unique-selling-points-usp)

---

## 1. Overview / Background

### 1.1 Background

India is undergoing one of the fastest EV adoption curves in the world. With government mandates under FAME II, state EV policies, and aggressive fleet electrification by players like Tata, Ola Electric, and Ather — the number of EVs on Indian roads is scaling rapidly. However, the charging infrastructure ecosystem has not kept pace with a unified, user-friendly experience.

Currently, EV charging in India is deeply fragmented:

- **Tata Power EZ Charge**, **ChargeZone**, **Ather Grid**, **BPCL Pulse**, **Statiq**, and **EESL** each operate their own siloed apps and networks.
- An EV owner in Bhopal may need 3–4 different apps just to find available chargers across the city.
- There is no unified real-time availability feed, no cross-network slot booking, and no EV-aware route planner for Indian roads.

This is the exact gap EVChargeFinder is designed to fill.

### 1.2 Problem Statement

EV users in India face three core pain points:

1. **Discovery Friction** — No single platform aggregates all charging stations across networks. Users waste time switching between apps or relying on outdated Google Maps pins.
2. **Availability Uncertainty** — Arriving at a charging station only to find all slots occupied is a critical barrier to EV adoption. There is no reliable real-time availability layer.
3. **No Reservation Capability** — Unlike fuel stations, EV charging requires 20–90 minutes per session. Without advance booking, long queues form, especially on highways and during peak hours. No Indian platform currently solves this end-to-end.

### 1.3 Context

This project is being developed for the **BGI Hackathon — Vision 2047 Viksit Bharat** under the Software category (Problem Statement ID: BT2P2), aligned with India's national vision of sustainable, tech-enabled smart mobility infrastructure.

---

## 2. Goals & Objectives

### 2.1 Primary Goals

- Build a **unified EV charging discovery and booking platform** that works across multiple charging networks in India.
- Provide **real-time slot availability** so users never arrive at a full station.
- Enable **advance slot reservations** to eliminate waiting time and improve infrastructure utilization.

### 2.2 Measurable Objectives

| Objective | Target Metric |
|---|---|
| Station Discovery Speed | User locates nearest available station in < 10 seconds |
| Booking Flow Completion | End-to-end booking completed in < 3 taps |
| Real-time Accuracy | Slot status refresh interval ≤ 5 seconds |
| Map Load Performance | Map renders within 2 seconds on 4G connection |
| Payment Success Rate | ≥ 98% transaction success on Razorpay |
| Admin Dashboard Uptime | 99.5% availability |

### 2.3 Business Objectives

- Demonstrate a scalable, India-first EV mobility platform viable for real-world deployment
- Showcase readiness for integration with OCPP-compliant charging hardware
- Establish a foundation extensible to fleet operator and B2B use cases

---

## 3. Scope

### 3.1 In-Scope

#### Core User App (React Native — Expo)
- Real-time map view of nearby EV charging stations
- Station detail pages (availability, charger type, pricing, wait time, ratings)
- Slot booking and reservation system with time-slot selection
- Booking management (view, modify, cancel)
- Navigation handoff to Google Maps / Apple Maps
- UPI-based payment via Razorpay
- User authentication (OTP-based, India-first)
- Push notifications for booking confirmations and slot reminders

#### Backend System (FastAPI)
- RESTful API for station data, user management, and bookings
- Real-time WebSocket layer for live slot availability updates
- Booking conflict resolution and slot locking logic
- Simulated IoT data feed for station status (for demo/MVP)
- Razorpay payment gateway integration

#### Admin Dashboard (React Native Web / Next.js)
- Station and slot management interface
- Live utilization monitoring
- Booking and revenue analytics
- Demand heatmap visualization

#### Data Layer
- PostgreSQL + PostGIS for geospatial station queries
- Supabase for Auth and Realtime

### 3.2 Out-of-Scope

- Native iOS App Store / Google Play Store submission (demo via Expo Go)
- Direct hardware integration with physical OCPP chargers (simulated in MVP)
- Multi-language / regional language UI (planned post-MVP)
- Loyalty/rewards program
- In-app customer support chat
- Integration with EV OEM platforms (e.g., Tata Motors Connect, Ather Connect)
- Carbon credit tracking or sustainability reporting

---

## 4. User Personas / Target Audience

### Persona 1 — Arjun, Personal EV Owner
> *28-year-old software engineer in Bhopal. Drives a Tata Nexon EV. Commutes daily and takes occasional weekend highway trips.*

- **Pain Point:** Can never be sure which ChargeZone or Tata Power station near his office is free. Has been stuck waiting 45 mins at a full station.
- **Goal:** Find a guaranteed available slot near his destination and book it before leaving home.
- **Tech Comfort:** High. Uses Swiggy, PhonePe, Google Maps daily.

---

### Persona 2 — Priya, Fleet Manager at an EV Cab Aggregator
> *35-year-old operations manager overseeing a fleet of 20 electric cabs in Bhopal.*

- **Pain Point:** Coordinating charging schedules for 20 vehicles across 3 networks is a logistical nightmare using separate apps.
- **Goal:** Plan and pre-book charging slots in bulk, view fleet charging status on a single dashboard.
- **Tech Comfort:** Medium. Needs clean, actionable UI.

---

### Persona 3 — Rahul, Highway Traveler
> *42-year-old business owner driving Hyundai Ioniq 5 from Bhopal to Indore.*

- **Pain Point:** Anxious about range on highway. Doesn't know which stations en route are operational and available.
- **Goal:** Plan a route with charging stops, knowing in advance whether slots are available at each stop.
- **Tech Comfort:** Medium-High.

---

### Persona 4 — Station Admin / Charging Network Operator
> *Manages 8 charging points across 2 locations in the city.*

- **Pain Point:** No visibility into utilization patterns, no way to manage bookings or update pricing dynamically.
- **Goal:** Monitor station health, manage slot schedules, view revenue analytics.
- **Tech Comfort:** Medium.

---

## 5. Functional Requirements

### 5.1 User Authentication

| ID | Requirement |
|---|---|
| FR-01 | Users must be able to register using mobile number + OTP (India-first flow) |
| FR-02 | Users must be able to log in via OTP or saved session |
| FR-03 | User profile must store vehicle type, connector preference, and payment methods |
| FR-04 | Admin accounts must have role-based access control (RBAC) |

### 5.2 Station Discovery

| ID | Requirement |
|---|---|
| FR-05 | App must request and use device GPS to show nearby stations on map |
| FR-06 | Map must display stations with color-coded availability markers (green = available, yellow = filling, red = full) |
| FR-07 | Users must be able to filter stations by charger type (AC Slow / DC Fast / CCS2 / CHAdeMO / Type 2), availability status, distance, and price range |
| FR-08 | Each station pin must show a summary tooltip (name, distance, available slots count) |
| FR-09 | List view must be available as an alternative to map view |
| FR-10 | Search must support location name / pincode input |

### 5.3 Station Detail

| ID | Requirement |
|---|---|
| FR-11 | Station detail screen must show: name, address, operating hours, total slots, available slots, charger types, pricing per unit/hour, estimated wait time, user ratings |
| FR-12 | Live slot availability must refresh every 5 seconds via WebSocket |
| FR-13 | Users must be able to view individual slot status (available / booked / in-use / offline) |
| FR-14 | Users must be able to rate and review a station post-visit |

### 5.4 Slot Booking

| ID | Requirement |
|---|---|
| FR-15 | Users must be able to select a date, time slot, and specific charger for booking |
| FR-16 | System must implement slot locking (2-minute hold) during payment to prevent race conditions |
| FR-17 | Booking confirmation must be sent via push notification and in-app notification |
| FR-18 | Users must be able to view all upcoming and past bookings |
| FR-19 | Users must be able to cancel a booking with defined cancellation policy (free cancellation > 30 mins before slot) |
| FR-20 | Booking must generate a unique QR code for station check-in |

### 5.5 Navigation

| ID | Requirement |
|---|---|
| FR-21 | "Navigate" CTA on station detail must deep-link to Google Maps / Apple Maps with destination pre-filled |
| FR-22 | Route planner must accept origin and destination and suggest charging stops along the route |
| FR-23 | Route planner must filter stops by real-time availability |

### 5.6 Payments

| ID | Requirement |
|---|---|
| FR-24 | Payment must be processed via Razorpay with UPI, UPI QR, and card support |
| FR-25 | Payment receipt must be stored in booking history |
| FR-26 | Refunds for cancellations must be auto-triggered via Razorpay Refunds API |
| FR-27 | Wallet/prepaid credit feature (optional enhancement) |

### 5.7 Admin Dashboard

| ID | Requirement |
|---|---|
| FR-28 | Admin must be able to add, edit, and deactivate stations and individual slots |
| FR-29 | Dashboard must show real-time occupancy across all managed stations |
| FR-30 | Admin must be able to view booking logs with user details, timestamps, and payment status |
| FR-31 | Analytics view must show daily/weekly/monthly utilization, revenue, and peak demand hours |
| FR-32 | Demand heatmap must visualize booking density by time-of-day and day-of-week |

### 5.8 Notifications

| ID | Requirement |
|---|---|
| FR-33 | Push notification must be sent on booking confirmation, 15 mins before slot, and on cancellation |
| FR-34 | Notification must be sent when a previously unavailable nearby station gains a free slot |

---

## 6. Non-Functional Requirements

### 6.1 Performance
- API response time: < 200ms for 95th percentile under normal load
- Map rendering: < 2 seconds on 4G connection
- WebSocket slot updates: ≤ 5-second latency
- App cold start time: < 3 seconds on mid-range Android device

### 6.2 Scalability
- Backend must support horizontal scaling via containerized deployment (Docker)
- Database must support PostGIS geospatial indexing for sub-100ms radius queries across 10,000+ stations
- Architecture must support multi-city / multi-network expansion without core refactor

### 6.3 Security
- All API endpoints must require JWT-based authentication
- Payment data must never be stored server-side (Razorpay tokenization)
- OTP-based auth with rate limiting (max 5 attempts per 10 minutes)
- HTTPS enforced across all endpoints
- Slot lock mechanism must be atomic (DB-level transaction) to prevent double booking

### 6.4 Reliability
- Backend uptime SLA: 99.5%
- Booking data must be persisted with ACID compliance
- Failed payments must not confirm bookings (transactional integrity)

### 6.5 Usability
- App must be fully functional on Android 10+ and iOS 14+
- UI must meet WCAG 2.1 AA accessibility standards
- Core booking flow must be completable in ≤ 3 taps from map view

### 6.6 Compliance
- User data handling must comply with India's **Digital Personal Data Protection Act (DPDPA) 2023**
- Payment processing must comply with **RBI tokenization guidelines**

---

## 7. User Stories / Use Cases

### UC-01: Discover Nearest Available Station

**Actor:** Arjun (Personal EV Owner)
**Precondition:** App is open, GPS is enabled
**Flow:**
1. App loads map centered on Arjun's current location
2. Green/yellow/red pins show nearby stations with availability
3. Arjun taps a green pin → sees station summary (2 slots free, DC Fast, ₹18/unit)
4. Taps "View Details" → full station page loads
5. Taps "Navigate" → Google Maps opens with destination set

**Postcondition:** User is en route to a confirmed available station

---

### UC-02: Book a Charging Slot in Advance

**Actor:** Rahul (Highway Traveler)
**Precondition:** User is logged in, viewing station detail
**Flow:**
1. Rahul opens Route Planner, enters Bhopal → Indore
2. System suggests 2 charging stops with available slots
3. He selects a station at Hoshangabad, taps "Book Slot"
4. Selects date: today, time: 2:00 PM – 2:45 PM, Slot #3 (CCS2)
5. Slot is locked for 2 minutes while he proceeds to payment
6. Pays ₹180 via UPI — confirmation screen shows QR code
7. Push notification sent: "Slot booked at Hoshangabad ChargePoint"

**Postcondition:** Slot is reserved, Rahul travels with confidence

---

### UC-03: Fleet Operator Manages Charging Schedule

**Actor:** Priya (Fleet Manager)
**Precondition:** Logged into Admin Dashboard
**Flow:**
1. Priya views fleet utilization dashboard
2. Sees 3 vehicles below 20% battery, due back at depot by 6 PM
3. Books 3 consecutive slots at nearest station for 6:30 PM, 7:00 PM, 7:30 PM
4. Receives confirmation for all three bookings

**Postcondition:** Fleet charging is planned, no overlap or waiting

---

### UC-04: Admin Updates Station Availability

**Actor:** Station Operator
**Precondition:** Logged into Admin Panel
**Flow:**
1. Operator marks Slot #2 as "Offline" due to hardware fault
2. System immediately updates live availability for all users viewing that station
3. Any pending bookings for that slot are flagged for rebooking/refund

**Postcondition:** Users see accurate availability, no one arrives at a broken charger

---

## 8. Wireframes / Mockups

> *Full high-fidelity mockups to be designed in Figma. Below are screen-level descriptions.*

### Screen 1 — Home / Map View
- Full-screen map (Google Maps SDK)
- Bottom sheet showing nearest 3 stations with quick stats
- FAB for filters (charger type, distance, availability)
- Top search bar for location input

### Screen 2 — Station Detail
- Hero section: Station name, network badge (Tata Power / ChargeZone etc.), rating
- Live availability grid: visual slot layout (green / red / grey tiles)
- Charger specs, pricing, operating hours
- "Book Now" and "Navigate" CTAs

### Screen 3 — Booking Flow
- Step 1: Date & time slot picker (calendar + time grid)
- Step 2: Charger selection (available slots highlighted)
- Step 3: Payment summary + Razorpay checkout
- Step 4: Confirmation screen with QR code

### Screen 4 — My Bookings
- Upcoming bookings with countdown timer
- Past bookings with receipt download
- Cancel / Modify options

### Screen 5 — Admin Dashboard
- KPI cards: Total bookings today, Revenue, Occupancy rate, Active stations
- Live station grid with real-time slot status
- Revenue trend chart (7-day)
- Demand heatmap (time-of-day × day-of-week)

---

## 9. Acceptance Criteria

| Feature | Acceptance Criterion |
|---|---|
| Station Discovery | User can see all stations within 10 km radius within 2 seconds of app load |
| Real-time Availability | Slot status changes propagate to all active clients within 5 seconds |
| Slot Booking | A confirmed booking is guaranteed unique — no double bookings possible |
| Payment | Booking is only confirmed after successful Razorpay payment callback |
| Cancellation | Cancellation within policy triggers auto-refund within 2 business days |
| Navigation | "Navigate" button launches external map app with correct coordinates in < 1 second |
| Admin Panel | Admin can toggle slot status and see reflection on user app within 5 seconds |
| Authentication | OTP login works end-to-end within 30 seconds |
| Notifications | Booking confirmation notification arrives within 10 seconds of payment |

---

## 10. Dependencies

### External APIs & Services

| Dependency | Purpose | Criticality |
|---|---|---|
| Google Maps Platform | Map rendering, geocoding, navigation | Critical |
| MapmyIndia Maps API | India-specific POI data (fallback/supplement) | Medium |
| Razorpay | UPI + card payment processing | Critical |
| Supabase | Auth, Realtime, Database hosting | Critical |
| Expo Push Notifications | Mobile push notifications | High |
| Firebase (optional) | Alternative push notification service | Low |

### Internal Dependencies

| Dependency | Description |
|---|---|
| Simulated IoT Data Service | Mock charging station status feed for MVP demo |
| Seed Data Set | Pre-populated station data for Bhopal (20–30 stations) for demo |
| PostGIS Extension | Must be enabled on PostgreSQL instance for geospatial queries |

### Industry Standards Referenced

| Standard | Relevance |
|---|---|
| OCPP 1.6 / 2.0.1 | Open Charge Point Protocol — architecture is designed to be OCPP-compatible for future hardware integration |
| BIS IS 17017 | Indian standard for EV charging infrastructure — informs charger type taxonomy |

---

## 11. Risks & Assumptions

### 11.1 Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| No access to real charging station data APIs | High | High | Use simulated/seeded station data for MVP; architecture supports real API swap |
| Race condition in slot booking under concurrent load | Medium | High | Implement DB-level atomic slot locking with 2-minute expiry |
| Google Maps API cost overrun during demo | Low | Medium | Cache map tiles, use static maps for non-critical screens |
| Razorpay sandbox limitations during demo | Low | Medium | Test all flows in sandbox thoroughly pre-hackathon |
| WebSocket connection drops on mobile networks | Medium | Medium | Implement reconnection logic + polling fallback |
| GPS accuracy issues indoors | Low | Low | Allow manual location input as fallback |

### 11.2 Assumptions

- Charging station data will be seeded manually for the Bhopal region for demo purposes
- Real OCPP hardware integration is out of scope; IoT status will be simulated
- Users have Android 10+ or iOS 14+ devices with GPS enabled
- Internet connectivity is available during app usage (no full offline mode)
- Razorpay sandbox environment will be used for payment demo (no real transactions)
- Team has access to Google Maps Platform API key with required APIs enabled

---

## 12. Timeline / Milestones

### Pre-Hackathon Build (Now → 12th May 2026)

| Phase | Deliverable | Target |
|---|---|---|
| **Phase 1** | DB schema finalized, FastAPI project scaffolded, Supabase configured | Week 1 |
| **Phase 2** | Station discovery API + Map view in React Native working | Week 2 |
| **Phase 3** | Booking flow + WebSocket real-time layer complete | Week 3 |
| **Phase 4** | Razorpay payment integration + Admin Dashboard MVP | Week 4 |
| **Phase 5** | End-to-end testing, bug fixes, seed data for Bhopal | Week 5 |
| **Phase 6** | UI polish, animations, demo script preparation | Week 6 (Pre-event) |

### During Hackathon (13th–14th May 2026)

| Time | Activity |
|---|---|
| Hour 0–4 | AI demand prediction feature + UI polish |
| Hour 4–8 | Route planner with charging stops |
| Hour 8–20 | Buffer for bugs, edge cases, demo rehearsal |
| Hour 20–30 | Presentation deck, system architecture diagram |
| Hour 30–36 | Final demo prep, dry run, submission |

---

## 13. Unique Selling Points (USP)

### 1. 🇮🇳 India-First, Not India-Adapted
Most EV apps are global products retrofitted for India. EVChargeFinder is built ground-up for the Indian market:
- **UPI-first payment flow** (not cards, not wallets — UPI is how India pays)
- **MapmyIndia integration** for superior India-specific road and POI data
- **OTP-based auth** — no email/password friction, exactly how Indian apps work
- **Multi-network aggregation** — Tata Power, ChargeZone, Statiq, Ather Grid all in one map

### 2. ⚡ Real-Time Slot Locking (No Double Booking)
No existing Indian EV app offers true slot reservation with conflict prevention. Our atomic DB-level slot locking mechanism ensures that when you book a slot, it's guaranteed — not first-come-first-served chaos at the station.

### 3. 🗺️ EV-Aware Route Planner
Unlike Google Maps which shows charging stations as generic pins, our route planner is EV-native — it factors in battery range, suggests charging stops, and shows real-time availability at each stop *before* you leave. Built specifically for Indian highways and tier-2 city corridors.

### 4. 👥 Fleet Operator Support
India's EV revolution is being driven as much by fleet electrification (Ola, BluSmart, Rapido EVs) as by personal ownership. We are the only solution in this hackathon addressing the **B2B fleet charging use case** — bulk bookings, schedule management, and utilization analytics for fleet managers.

### 5. 🤖 AI Demand Prediction
ML-based heatmap predicting charging demand by location, time-of-day, and day-of-week. Stations can use this to dynamically price slots (higher demand = higher price), while users can plan around predicted availability. This moves the product from reactive to proactive.

### 6. 🔌 OCPP-Ready Architecture
While the MVP simulates IoT data, the backend is architected to be **OCPP 1.6 / 2.0.1 compliant** — the global open standard for EV charger communication. This means zero core refactoring is needed to plug in real hardware. Judges and evaluators familiar with the EV industry will recognize this as production-readiness, not just a hackathon prototype.

---

*Document End — EVChargeFinder PRD v1.0*
*Next Document: System Architecture & API Design Specification*
