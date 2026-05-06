# Backend Endpoint Map

> Last updated: `2026-05-07`  
> Backend repo: `C:\Users\Lenovo\Backend-Ev`  
> Frontend repo reviewed: `C:\Users\Lenovo\Kairo-React-Native`

## Summary

The backend already exposes the core APIs the current React Native app uses for:

- auth
- profile bootstrap and update
- nearby station discovery
- station detail
- slot listing
- bookings
- payment verification and Razorpay webhook reconciliation
- route planning
- notifications
- demand/pricing read paths
- station reviews read path

The biggest remaining backend product gap is still:

- real station inventory data in the `stations` table

The main remaining end-to-end gaps are shared with the frontend:

- discovery and route planning still need live GPS as the real origin
- frontend still needs real WebSocket slot sync
- frontend still needs the final live payment SDK flow

## Base API

- Local dev base URL: `http://127.0.0.1:8000/v1`
- Docs UI: `http://127.0.0.1:8000/docs`
- Protected routes use Bearer JWT auth
- OTP auth is development-friendly and can expose `dev_otp` in non-production workflows

## Core App Endpoints

### Auth

| Method | Endpoint | Used by frontend | Status |
|---|---|---|---|
| `POST` | `/v1/auth/otp/send` | Yes | Live |
| `POST` | `/v1/auth/otp/verify` | Yes | Live |
| `POST` | `/v1/auth/token/refresh` | Yes | Live |
| `GET` | `/v1/auth/me` | Yes | Live |
| `PATCH` | `/v1/auth/me` | Yes | Live |
| `DELETE` | `/v1/auth/logout` | Yes | Live |

Notes:

- current user bootstrap is part of the active frontend session flow
- refresh flow is already consumed by the frontend Axios interceptor

### Stations

| Method | Endpoint | Used by frontend | Status |
|---|---|---|---|
| `GET` | `/v1/stations/nearby` | Yes | Live |
| `GET` | `/v1/stations/{station_id}` | Yes | Live |

Notes:

- APIs are integrated, but the backend database still has no real station inventory loaded
- once stations are seeded with real lat/lng, map rendering and list discovery can use them immediately

### Slots

| Method | Endpoint | Used by frontend | Status |
|---|---|---|---|
| `GET` | `/v1/slots/stations/{station_id}` | Yes | Live |
| `GET` | `/v1/slots/{slot_id}` | Not used in current mobile UI | Backend only |

Notes:

- slot fetch is already wired
- live slot updates exist server-side, but the frontend still uses mock/polling behavior

### Bookings

| Method | Endpoint | Used by frontend | Status |
|---|---|---|---|
| `POST` | `/v1/bookings` | Yes | Live |
| `GET` | `/v1/bookings` | Yes | Live |
| `DELETE` | `/v1/bookings/{booking_id}` | Yes | Live |

### Payments

| Method | Endpoint | Used by frontend | Status |
|---|---|---|---|
| `POST` | `/v1/payments/verify` | Yes | Live |
| `POST` | `/v1/payments/webhook` | Backend-only Razorpay callback | Live |

Notes:

- backend-side reconciliation is in place
- webhook confirmation flow is covered by integration tests
- the mobile client should not own financial rollback logic

### Routes

| Method | Endpoint | Used by frontend | Status |
|---|---|---|---|
| `POST` | `/v1/routes/plan` | Yes | Live |

Notes:

- route planning is backend-powered
- frontend still needs live device GPS for the true origin instead of demo coordinates

### Notifications

| Method | Endpoint | Used by frontend | Status |
|---|---|---|---|
| `GET` | `/v1/notifications` | Yes | Live |
| `POST` | `/v1/notifications/{notification_id}/read` | Yes | Live |
| `POST` | `/v1/notifications/read-all` | Yes | Live |

### Demand

| Method | Endpoint | Used by frontend | Status |
|---|---|---|---|
| `GET` | `/v1/demand/predict/{station_id}` | Yes | Live |
| `GET` | `/v1/demand/pricing/{station_id}` | Yes | Live |
| `POST` | `/v1/demand/train/{station_id}` | No | Admin/backend only |

### Reviews

| Method | Endpoint | Used by frontend | Status |
|---|---|---|---|
| `GET` | `/v1/reviews/stations/{station_id}` | Yes | Live |
| `POST` | `/v1/reviews` | No submission UI yet | Backend exists |

## Backend-Only / Not Yet Consumed Fully

### Admin

| Method | Endpoint | Status |
|---|---|---|
| `PATCH` | `/v1/admin/stations/{station_id}/slots/{slot_id}` | Backend only |
| `GET` | `/v1/admin/stations/{station_id}/bookings` | Backend only |

### IoT / Realtime / Ops

| Method | Endpoint | Status |
|---|---|---|
| `POST` | `/v1/iot/heartbeat` | Backend only |
| `GET` | `/metrics` | Backend only |
| WebSocket | `app/routers/ws.py` and `app/routers/websockets.py` | Server exists, frontend not fully wired |

## Current Reality Check

### Integrated and working with the app

- OTP send / verify / refresh
- current user bootstrap
- profile update
- bookings create / list / cancel
- payment verification
- notification list / mark-read / mark-all-read
- route planning
- station detail and nearby station APIs
- slot list fetch
- demand and pricing reads
- station review reads

### Still incomplete from a full product-launch perspective

- real station inventory data
- live GPS-based origin from the frontend
- real frontend WebSocket slot sync
- final live payment SDK flow on the mobile client
- review submission UI
- wallet / balance endpoints
- richer profile summary endpoints

## Recommended Next Update Trigger

Update this file again when any of the following land:

- station import or seeding pipeline
- live GPS origin rollout
- real frontend websocket subscription to slot updates
- wallet/profile-summary backend endpoints
- real mobile payment SDK integration
