# API Specification
## EVChargeFinder — REST API v1

---

| Field | Details |
|---|---|
| **Document Version** | v1.0 |
| **Status** | Draft |
| **Author** | Shubhranshu Das (Reesh) |
| **Date** | April 2026 |
| **Base URL (Dev)** | `http://localhost:8000/v1` |
| **Base URL (Prod)** | `https://api.evchargefinder.in/v1` |
| **Reference HLD** | HLD_TRD_EVChargeFinder v1.0 |

---

## Table of Contents

1. [Global Conventions](#1-global-conventions)
2. [Error Schema](#2-error-schema)
3. [Authentication API](#3-authentication-api)
4. [Stations API](#4-stations-api)
5. [Slots API](#5-slots-api)
6. [Bookings API](#6-bookings-api)
7. [Payments API](#7-payments-api)
8. [Route Planner API](#8-route-planner-api)
9. [Reviews API](#9-reviews-api)
10. [Notifications API](#10-notifications-api)
11. [Admin API](#11-admin-api)
12. [WebSocket Events](#12-websocket-events)
13. [Rate Limits Reference](#13-rate-limits-reference)
14. [Status Code Reference](#14-status-code-reference)

---

## 1. Global Conventions

### 1.1 Request Headers

| Header | Required | Description |
|---|---|---|
| `Content-Type` | Yes (POST/PATCH) | Always `application/json` |
| `Authorization` | Yes (protected routes) | `Bearer <access_token>` |
| `Idempotency-Key` | Yes (POST /bookings, /payments) | UUID v4 — prevents duplicate operations |
| `X-App-Version` | Recommended | React Native app version e.g. `1.0.4` |
| `Accept-Language` | Optional | `en-IN` (default), `hi-IN` |

### 1.2 Response Envelope

All successful responses follow this envelope:

```json
{
  "success": true,
  "data": { ... },
  "meta": {
    "timestamp": "2026-05-13T08:00:00Z",
    "request_id": "req_abc123"
  }
}
```

Paginated responses additionally include:

```json
{
  "success": true,
  "data": [...],
  "pagination": {
    "total": 120,
    "limit": 20,
    "offset": 0,
    "has_next": true,
    "has_prev": false
  },
  "meta": { ... }
}
```

### 1.3 Timestamp Format

All timestamps are **ISO 8601 with timezone offset**:
```
2026-05-13T14:00:00+05:30   ← IST (preferred for India)
2026-05-13T08:30:00Z        ← UTC (accepted)
```

### 1.4 Currency

All monetary values are in **INR (₹)** as `DECIMAL(10, 2)`. Example: `180.00`

### 1.5 Coordinate Format

All geographic coordinates use **WGS84 (EPSG:4326)**:
```json
{ "lat": 23.2599, "lng": 77.4126 }
```

---

## 2. Error Schema

### 2.1 Standard Error Response

```json
{
  "success": false,
  "error": {
    "code": "SLOT_UNAVAILABLE",
    "message": "This slot is already booked for the selected time window.",
    "details": {
      "slot_id": "uuid",
      "conflicting_window": {
        "start": "2026-05-13T14:00:00+05:30",
        "end": "2026-05-13T14:45:00+05:30"
      }
    }
  },
  "meta": {
    "timestamp": "2026-05-13T08:00:00Z",
    "request_id": "req_abc123"
  }
}
```

### 2.2 Error Code Registry

| HTTP Status | Error Code | Meaning |
|---|---|---|
| 400 | `VALIDATION_ERROR` | Request body failed Pydantic schema validation |
| 400 | `INVALID_TIME_WINDOW` | scheduled_end ≤ scheduled_start |
| 400 | `PAST_TIME_WINDOW` | Booking time is in the past |
| 401 | `UNAUTHORIZED` | Missing or invalid JWT |
| 401 | `TOKEN_EXPIRED` | Access token has expired |
| 401 | `INVALID_OTP` | OTP does not match or has expired |
| 403 | `FORBIDDEN` | Authenticated but insufficient role |
| 404 | `STATION_NOT_FOUND` | No station with given ID |
| 404 | `SLOT_NOT_FOUND` | No slot with given ID |
| 404 | `BOOKING_NOT_FOUND` | No booking with given ID |
| 409 | `SLOT_UNAVAILABLE` | Slot is locked, booked, or in use |
| 409 | `SLOT_LOCKED` | Slot is temporarily locked by another user |
| 409 | `DUPLICATE_REQUEST` | Idempotency key already used |
| 409 | `BOOKING_NOT_CANCELLABLE` | Booking status does not allow cancellation |
| 422 | `PAYMENT_VERIFICATION_FAILED` | Razorpay signature mismatch |
| 422 | `WEBHOOK_SIGNATURE_INVALID` | Webhook payload signature invalid |
| 429 | `RATE_LIMITED` | Too many requests |
| 429 | `OTP_LIMIT_EXCEEDED` | Max OTP attempts reached |
| 500 | `INTERNAL_ERROR` | Unexpected server error |
| 503 | `PAYMENT_GATEWAY_ERROR` | Razorpay API unavailable |

---

## 3. Authentication API

### 3.1 Send OTP

```
POST /auth/otp/send
Authorization: None
Rate Limit: 3 req/phone/10min
```

**Request:**
```json
{
  "phone": "+919876543210"
}
```

**Validation:**
- `phone` must match regex `^\+91[6-9]\d{9}$` (Indian mobile numbers only)

**Response 200:**
```json
{
  "success": true,
  "data": {
    "message": "OTP sent successfully",
    "expires_in_seconds": 300,
    "phone": "+919876543210"
  }
}
```

**Response 429 — OTP rate limited:**
```json
{
  "success": false,
  "error": {
    "code": "OTP_LIMIT_EXCEEDED",
    "message": "Maximum OTP requests reached. Please try again after 10 minutes.",
    "details": { "retry_after_seconds": 547 }
  }
}
```

---

### 3.2 Verify OTP

```
POST /auth/otp/verify
Authorization: None
```

**Request:**
```json
{
  "phone": "+919876543210",
  "otp": "482910"
}
```

**Response 200:**
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "Bearer",
    "access_token_expires_in": 900,
    "refresh_token_expires_in": 604800,
    "user": {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "phone": "+919876543210",
      "name": null,
      "role": "user",
      "vehicle_type": null,
      "preferred_connector": null,
      "is_new_user": true,
      "created_at": "2026-05-13T08:00:00Z"
    }
  }
}
```

**Response 401 — Invalid OTP:**
```json
{
  "success": false,
  "error": {
    "code": "INVALID_OTP",
    "message": "The OTP entered is incorrect or has expired.",
    "details": { "attempts_remaining": 3 }
  }
}
```

---

### 3.3 Refresh Token

```
POST /auth/token/refresh
Authorization: None
```

**Request:**
```json
{
  "refresh_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response 200:**
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
    "expires_in": 900
  }
}
```

---

### 3.4 Get Current User

```
GET /auth/me
Authorization: Bearer <access_token>
```

**Response 200:**
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "phone": "+919876543210",
    "name": "Arjun Sharma",
    "email": "arjun@example.com",
    "role": "user",
    "vehicle_type": "Tata Nexon EV",
    "preferred_connector": "CCS2",
    "expo_push_token": "ExponentPushToken[xxx]",
    "is_active": true,
    "created_at": "2026-05-13T08:00:00Z"
  }
}
```

---

### 3.5 Update Profile

```
PATCH /auth/me
Authorization: Bearer <access_token>
```

**Request:**
```json
{
  "name": "Arjun Sharma",
  "email": "arjun@example.com",
  "vehicle_type": "Tata Nexon EV",
  "preferred_connector": "CCS2",
  "expo_push_token": "ExponentPushToken[xxx]"
}
```

All fields optional. Only provided fields are updated (partial update).

**Response 200:** Returns updated user object (same as GET /auth/me)

---

### 3.6 Logout

```
DELETE /auth/logout
Authorization: Bearer <access_token>
```

Blacklists the current JWT's `jti` in Redis (TTL matching remaining token lifetime).

**Response 200:**
```json
{
  "success": true,
  "data": { "message": "Logged out successfully" }
}
```

---

## 4. Stations API

### 4.1 Nearby Stations Search

```
GET /stations/nearby
Authorization: Bearer <access_token>
```

The **most performance-critical endpoint** in the system. Backed by PostGIS ST_DWithin with GIST index.

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `lat` | float | ✅ | — | User latitude (WGS84) |
| `lng` | float | ✅ | — | User longitude (WGS84) |
| `radius_km` | float | ❌ | `10` | Search radius in kilometers (max: 100) |
| `charger_type` | string | ❌ | — | Filter: `AC_SLOW`, `AC_FAST`, `DC_FAST`, `CCS2`, `CHAdeMO`, `TYPE2`, `BHARAT_AC`, `BHARAT_DC` |
| `available_only` | bool | ❌ | `false` | Only show stations with ≥1 available slot |
| `min_power_kw` | float | ❌ | — | Minimum charger power output |
| `network` | string | ❌ | — | Filter by network operator |
| `limit` | int | ❌ | `20` | Max results (max: 50) |
| `offset` | int | ❌ | `0` | Pagination offset |

**Example Request:**
```
GET /stations/nearby?lat=23.2599&lng=77.4126&radius_km=10&charger_type=CCS2&available_only=true&limit=20
```

**Response 200:**
```json
{
  "success": true,
  "data": {
    "stations": [
      {
        "id": "550e8400-e29b-41d4-a716-446655440001",
        "name": "Tata Power EZ Charge — DB Mall",
        "network": "TATA_POWER",
        "distance_km": 1.24,
        "location": {
          "lat": 23.2334,
          "lng": 77.4307
        },
        "address": {
          "line1": "DB Mall, MP Nagar Zone-1",
          "city": "Bhopal",
          "state": "Madhya Pradesh",
          "pincode": "462011"
        },
        "available_slots": 3,
        "total_slots": 8,
        "charger_types": ["CCS2", "TYPE2"],
        "max_power_kw": 50.0,
        "price_per_unit": 18.00,
        "price_per_hour": null,
        "avg_rating": 4.3,
        "total_reviews": 47,
        "operating_hours": {
          "open": "06:00",
          "close": "23:00",
          "days": [1, 2, 3, 4, 5, 6, 7]
        },
        "amenities": ["parking", "wifi", "food"],
        "is_active": true,
        "estimated_wait_minutes": 0
      },
      {
        "id": "550e8400-e29b-41d4-a716-446655440002",
        "name": "ChargeZone — Arera Colony",
        "network": "CHARGE_ZONE",
        "distance_km": 2.87,
        "location": {
          "lat": 23.2156,
          "lng": 77.4389
        },
        "address": {
          "line1": "E-5, Arera Colony",
          "city": "Bhopal",
          "state": "Madhya Pradesh",
          "pincode": "462016"
        },
        "available_slots": 0,
        "total_slots": 4,
        "charger_types": ["CCS2", "CHAdeMO"],
        "max_power_kw": 60.0,
        "price_per_unit": 16.50,
        "price_per_hour": null,
        "avg_rating": 3.9,
        "total_reviews": 23,
        "operating_hours": {
          "open": "00:00",
          "close": "23:59",
          "days": [1, 2, 3, 4, 5, 6, 7]
        },
        "amenities": ["parking"],
        "is_active": true,
        "estimated_wait_minutes": 22
      }
    ],
    "search_meta": {
      "lat": 23.2599,
      "lng": 77.4126,
      "radius_km": 10,
      "total_found": 12,
      "available_count": 7
    }
  },
  "pagination": {
    "total": 12,
    "limit": 20,
    "offset": 0,
    "has_next": false,
    "has_prev": false
  }
}
```

---

### 4.2 Get Station Detail

```
GET /stations/:id
Authorization: Bearer <access_token>
```

**Path Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `id` | UUID | Station ID |

**Response 200:**
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "name": "Tata Power EZ Charge — DB Mall",
    "network": "TATA_POWER",
    "location": { "lat": 23.2334, "lng": 77.4307 },
    "address": {
      "line1": "DB Mall, MP Nagar Zone-1",
      "line2": "Ground Floor, Parking Level",
      "city": "Bhopal",
      "state": "Madhya Pradesh",
      "pincode": "462011"
    },
    "total_slots": 8,
    "available_slots": 3,
    "slots": [
      {
        "id": "uuid",
        "slot_number": 1,
        "charger_type": "CCS2",
        "power_kw": 50.0,
        "status": "AVAILABLE",
        "connector_count": 1
      },
      {
        "id": "uuid",
        "slot_number": 2,
        "charger_type": "CCS2",
        "power_kw": 50.0,
        "status": "BOOKED",
        "connector_count": 1
      },
      {
        "id": "uuid",
        "slot_number": 3,
        "charger_type": "TYPE2",
        "power_kw": 22.0,
        "status": "IN_USE",
        "connector_count": 1
      }
    ],
    "operating_hours": {
      "open": "06:00",
      "close": "23:00",
      "days": [1, 2, 3, 4, 5, 6, 7]
    },
    "pricing": {
      "price_per_unit": 18.00,
      "price_per_hour": null,
      "currency": "INR",
      "billing_type": "per_kwh"
    },
    "amenities": ["parking", "wifi", "food", "restroom"],
    "avg_rating": 4.3,
    "total_reviews": 47,
    "is_active": true,
    "is_verified": true,
    "ocpp_station_id": "BHOPAL-DBMALL-001",
    "last_heartbeat": "2026-05-13T07:58:12Z"
  }
}
```

---

### 4.3 Search Stations by Text

```
GET /stations/search
Authorization: Bearer <access_token>
```

**Query Parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `q` | string | ✅ | Search query (station name, area, pincode) |
| `limit` | int | ❌ | Max 20 |

Uses PostgreSQL `pg_trgm` trigram index for fuzzy text matching.

**Response 200:** Same station list structure as `/stations/nearby` without distance fields.

---

## 5. Slots API

### 5.1 Get Station Slots with Availability Windows

```
GET /stations/:station_id/slots
Authorization: Bearer <access_token>
```

**Query Parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `date` | string | ✅ | Date in `YYYY-MM-DD` format (IST) |
| `charger_type` | string | ❌ | Filter by charger type |

Returns each slot's availability timeline for the requested date — used to render the time-slot picker in the booking flow.

**Response 200:**
```json
{
  "success": true,
  "data": {
    "station_id": "uuid",
    "date": "2026-05-13",
    "slots": [
      {
        "id": "uuid",
        "slot_number": 1,
        "charger_type": "CCS2",
        "power_kw": 50.0,
        "current_status": "AVAILABLE",
        "booked_windows": [
          {
            "start": "2026-05-13T10:00:00+05:30",
            "end": "2026-05-13T10:45:00+05:30"
          },
          {
            "start": "2026-05-13T14:00:00+05:30",
            "end": "2026-05-13T14:45:00+05:30"
          }
        ],
        "available_from": "2026-05-13T06:00:00+05:30",
        "available_until": "2026-05-13T23:00:00+05:30"
      },
      {
        "id": "uuid",
        "slot_number": 2,
        "charger_type": "CCS2",
        "power_kw": 50.0,
        "current_status": "OFFLINE",
        "booked_windows": [],
        "available_from": null,
        "available_until": null
      }
    ]
  }
}
```

---

## 6. Bookings API

### 6.1 Create Booking

```
POST /bookings
Authorization: Bearer <access_token>
Idempotency-Key: <uuid-v4>   ← REQUIRED
```

This endpoint:
1. Acquires a 2-minute Redis distributed lock on the slot
2. Creates a Razorpay order
3. Inserts a `PENDING_PAYMENT` booking record
4. Returns Razorpay order details for client-side payment

**Request:**
```json
{
  "slot_id": "550e8400-e29b-41d4-a716-446655440010",
  "scheduled_start": "2026-05-13T14:00:00+05:30",
  "scheduled_end": "2026-05-13T14:45:00+05:30"
}
```

**Validation Rules:**
- `scheduled_start` must be at least 5 minutes in the future
- `scheduled_end` must be after `scheduled_start`
- Minimum booking duration: 15 minutes
- Maximum booking duration: 4 hours
- `scheduled_start` must fall within station operating hours

**Response 201:**
```json
{
  "success": true,
  "data": {
    "booking_id": "uuid",
    "status": "PENDING_PAYMENT",
    "slot": {
      "id": "uuid",
      "slot_number": 3,
      "charger_type": "CCS2",
      "power_kw": 50.0
    },
    "station": {
      "id": "uuid",
      "name": "Tata Power EZ Charge — DB Mall",
      "address": "DB Mall, MP Nagar, Bhopal"
    },
    "scheduled_start": "2026-05-13T14:00:00+05:30",
    "scheduled_end": "2026-05-13T14:45:00+05:30",
    "amount_charged": 180.00,
    "currency": "INR",
    "lock_expires_at": "2026-05-13T08:32:00Z",
    "payment": {
      "razorpay_order_id": "order_PQkXbH5z3mCXno",
      "razorpay_key_id": "rzp_test_xxxxxxxxxxx",
      "amount_paise": 18000,
      "currency": "INR"
    }
  }
}
```

**Response 409 — Slot unavailable:**
```json
{
  "success": false,
  "error": {
    "code": "SLOT_UNAVAILABLE",
    "message": "This slot is already booked for the selected time window.",
    "details": {
      "slot_id": "uuid",
      "conflicting_window": {
        "start": "2026-05-13T14:00:00+05:30",
        "end": "2026-05-13T14:45:00+05:30"
      }
    }
  }
}
```

**Response 409 — Slot locked by another user:**
```json
{
  "success": false,
  "error": {
    "code": "SLOT_LOCKED",
    "message": "This slot is temporarily reserved by another user.",
    "details": { "locked_for_seconds": 87 }
  }
}
```

**Response 409 — Duplicate idempotency key:**
```json
{
  "success": false,
  "error": {
    "code": "DUPLICATE_REQUEST",
    "message": "A booking with this idempotency key already exists.",
    "details": { "existing_booking_id": "uuid" }
  }
}
```

---

### 6.2 Get User Bookings

```
GET /bookings
Authorization: Bearer <access_token>
```

**Query Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `status` | string | — | Filter: `CONFIRMED`, `ACTIVE`, `COMPLETED`, `CANCELLED` |
| `upcoming` | bool | `false` | Only show future bookings |
| `limit` | int | `10` | Max 50 |
| `offset` | int | `0` | Pagination |

**Response 200:**
```json
{
  "success": true,
  "data": {
    "bookings": [
      {
        "id": "uuid",
        "status": "CONFIRMED",
        "qr_code": "a3f9e2b1c4d5e6f7a8b9c0d1e2f3a4b5",
        "station": {
          "id": "uuid",
          "name": "Tata Power EZ Charge — DB Mall",
          "address": "DB Mall, MP Nagar, Bhopal",
          "location": { "lat": 23.2334, "lng": 77.4307 }
        },
        "slot": {
          "slot_number": 3,
          "charger_type": "CCS2",
          "power_kw": 50.0
        },
        "scheduled_start": "2026-05-13T14:00:00+05:30",
        "scheduled_end": "2026-05-13T14:45:00+05:30",
        "amount_charged": 180.00,
        "created_at": "2026-05-13T07:30:00Z"
      }
    ]
  },
  "pagination": {
    "total": 8,
    "limit": 10,
    "offset": 0,
    "has_next": false,
    "has_prev": false
  }
}
```

---

### 6.3 Get Booking Detail

```
GET /bookings/:id
Authorization: Bearer <access_token>
```

Returns full booking detail including QR code, payment info, and energy consumed.

**Response 200:**
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "status": "CONFIRMED",
    "qr_code": "a3f9e2b1c4d5e6f7a8b9c0d1e2f3a4b5",
    "station": {
      "id": "uuid",
      "name": "Tata Power EZ Charge — DB Mall",
      "network": "TATA_POWER",
      "address": "DB Mall, MP Nagar Zone-1, Bhopal — 462011",
      "location": { "lat": 23.2334, "lng": 77.4307 },
      "phone": "+917612345678"
    },
    "slot": {
      "id": "uuid",
      "slot_number": 3,
      "charger_type": "CCS2",
      "power_kw": 50.0
    },
    "scheduled_start": "2026-05-13T14:00:00+05:30",
    "scheduled_end": "2026-05-13T14:45:00+05:30",
    "actual_start": null,
    "actual_end": null,
    "energy_consumed_kwh": null,
    "amount_charged": 180.00,
    "amount_refunded": 0.00,
    "payment": {
      "razorpay_payment_id": "pay_PQkXbH5z3mCXno",
      "method": "upi",
      "upi_vpa": "arjun@upi",
      "status": "SUCCESS",
      "paid_at": "2026-05-13T07:31:42Z"
    },
    "can_cancel": true,
    "cancel_deadline": "2026-05-13T13:30:00+05:30",
    "created_at": "2026-05-13T07:30:00Z"
  }
}
```

---

### 6.4 Cancel Booking

```
PATCH /bookings/:id/cancel
Authorization: Bearer <access_token>
```

**Request:**
```json
{
  "reason": "Change of plans"
}
```

**Cancellation Policy:**
- `scheduled_start - NOW() > 30 min` → Full refund
- `scheduled_start - NOW() ≤ 30 min` → No refund
- `status = ACTIVE` (charging in progress) → Cannot cancel

**Response 200:**
```json
{
  "success": true,
  "data": {
    "booking_id": "uuid",
    "status": "CANCELLED",
    "refund": {
      "eligible": true,
      "amount": 180.00,
      "razorpay_refund_id": "rfnd_xxx",
      "estimated_credit_days": 2
    },
    "message": "Booking cancelled. Full refund of ₹180.00 will be credited within 2 business days."
  }
}
```

**Response 409 — Cannot cancel:**
```json
{
  "success": false,
  "error": {
    "code": "BOOKING_NOT_CANCELLABLE",
    "message": "Charging session is already in progress and cannot be cancelled.",
    "details": { "current_status": "ACTIVE" }
  }
}
```

---

### 6.5 Check In (QR Code Scan)

```
POST /bookings/:id/checkin
Authorization: Bearer <access_token>  (Station operator's token)
```

Called when the station operator's device scans the user's QR code.

**Request:**
```json
{
  "qr_code": "a3f9e2b1c4d5e6f7a8b9c0d1e2f3a4b5",
  "station_id": "uuid"
}
```

**Response 200:**
```json
{
  "success": true,
  "data": {
    "booking_id": "uuid",
    "status": "ACTIVE",
    "user": {
      "name": "Arjun Sharma",
      "vehicle_type": "Tata Nexon EV"
    },
    "slot_number": 3,
    "actual_start": "2026-05-13T14:02:11+05:30",
    "scheduled_end": "2026-05-13T14:45:00+05:30"
  }
}
```

---

## 7. Payments API

### 7.1 Verify Payment (Client-Side)

```
POST /payments/verify
Authorization: Bearer <access_token>
Idempotency-Key: <uuid-v4>
```

Called immediately after Razorpay SDK returns a successful payment. Server verifies the HMAC-SHA256 signature and sets payment status to `PENDING_WEBHOOK`.

**Request:**
```json
{
  "booking_id": "uuid",
  "razorpay_order_id": "order_PQkXbH5z3mCXno",
  "razorpay_payment_id": "pay_PQkXbH5z3mCXno",
  "razorpay_signature": "9ef4dabb0212df56fcf35b56d05d3b8b0c0c0c0..."
}
```

**Response 200:**
```json
{
  "success": true,
  "data": {
    "payment_id": "uuid",
    "status": "PENDING_WEBHOOK",
    "message": "Payment verified. Awaiting final confirmation."
  }
}
```

**Response 422 — Signature mismatch:**
```json
{
  "success": false,
  "error": {
    "code": "PAYMENT_VERIFICATION_FAILED",
    "message": "Payment signature verification failed. Please contact support.",
    "details": { "booking_id": "uuid" }
  }
}
```

---

### 7.2 Razorpay Webhook

```
POST /payments/webhook
Authorization: None  ← No JWT. Validated by Razorpay-Signature header.
Content-Type: application/json
Razorpay-Signature: <hmac-sha256-hash>
```

This endpoint is called server-to-server by Razorpay. It is the **source of truth** for payment confirmation.

**Handled Events:**

| Event | Action |
|---|---|
| `payment.captured` | Confirm booking, mark slot BOOKED, send push |
| `payment.failed` | Release slot lock, mark booking CANCELLED |
| `refund.created` | Update payment refund fields |
| `refund.processed` | Mark payment REFUNDED |

**Request Body (Razorpay sends):**
```json
{
  "entity": "event",
  "account_id": "acc_xxx",
  "event": "payment.captured",
  "contains": ["payment"],
  "payload": {
    "payment": {
      "entity": {
        "id": "pay_PQkXbH5z3mCXno",
        "entity": "payment",
        "amount": 18000,
        "currency": "INR",
        "status": "captured",
        "order_id": "order_PQkXbH5z3mCXno",
        "method": "upi",
        "vpa": "arjun@upi",
        "captured": true
      }
    }
  },
  "created_at": 1747123200
}
```

**Response 200:**
```json
{ "status": "ok" }
```

> **Note:** Always return 200 quickly. Any processing errors must be handled internally — Razorpay retries on non-200 responses.

---

### 7.3 Get Payment Receipt

```
GET /payments/:booking_id
Authorization: Bearer <access_token>
```

**Response 200:**
```json
{
  "success": true,
  "data": {
    "payment_id": "uuid",
    "booking_id": "uuid",
    "razorpay_payment_id": "pay_PQkXbH5z3mCXno",
    "razorpay_order_id": "order_PQkXbH5z3mCXno",
    "amount": 180.00,
    "currency": "INR",
    "status": "SUCCESS",
    "method": "upi",
    "upi_vpa": "arjun@upi",
    "webhook_verified": true,
    "paid_at": "2026-05-13T07:31:42Z",
    "refund": null
  }
}
```

---

## 8. Route Planner API

### 8.1 Plan EV Route with Charging Stops

```
POST /routes/ev-plan
Authorization: Bearer <access_token>
```

**Request:**
```json
{
  "origin": {
    "lat": 23.2599,
    "lng": 77.4126,
    "label": "Bhopal"
  },
  "destination": {
    "lat": 22.7196,
    "lng": 75.8577,
    "label": "Indore"
  },
  "vehicle": {
    "range_km": 312,
    "current_battery_percent": 72,
    "preferred_connector": "CCS2",
    "usable_battery_kwh": 30.2
  },
  "preferences": {
    "min_arrival_battery_percent": 15,
    "charge_to_percent": 80,
    "avoid_tolls": false,
    "departure_time": "2026-05-13T09:00:00+05:30"
  }
}
```

**Response 200:**
```json
{
  "success": true,
  "data": {
    "route": {
      "origin": { "lat": 23.2599, "lng": 77.4126, "label": "Bhopal" },
      "destination": { "lat": 22.7196, "lng": 75.8577, "label": "Indore" },
      "total_distance_km": 193.4,
      "total_estimated_duration_min": 214,
      "driving_duration_min": 174,
      "total_charging_time_min": 40,
      "polyline": "wk`cDggq`LxBn@dDhA...",
      "charging_stops": [
        {
          "order": 1,
          "station": {
            "id": "uuid",
            "name": "ChargeZone — Hoshangabad",
            "network": "CHARGE_ZONE",
            "address": "NH-46, Hoshangabad, MP",
            "location": { "lat": 22.7519, "lng": 77.7260 }
          },
          "distance_from_origin_km": 78.2,
          "distance_to_destination_km": 115.2,
          "estimated_arrival_time": "2026-05-13T09:52:00+05:30",
          "battery_at_arrival_percent": 28,
          "recommended_charge_to_percent": 80,
          "estimated_charge_duration_min": 35,
          "estimated_departure_time": "2026-05-13T10:27:00+05:30",
          "battery_at_departure_percent": 80,
          "charger_type": "DC_FAST",
          "power_kw": 60.0,
          "price_per_unit": 15.50,
          "estimated_charge_cost": 54.25,
          "real_time_availability": {
            "available_slots": 2,
            "slot_ids": ["uuid1", "uuid2"],
            "next_available_window": "2026-05-13T09:45:00+05:30"
          }
        }
      ],
      "summary": {
        "charging_stops_count": 1,
        "total_estimated_charge_cost": 54.25,
        "will_reach_destination": true,
        "battery_at_destination_percent": 31
      }
    }
  }
}
```

---

### 8.2 Get Demand Forecast for Station

```
GET /stations/:id/demand-forecast
Authorization: Bearer <access_token>
```

**Query Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `date` | string | Today | Date in `YYYY-MM-DD` |

**Response 200:**
```json
{
  "success": true,
  "data": {
    "station_id": "uuid",
    "date": "2026-05-13",
    "forecast": [
      { "hour": 6, "predicted_bookings": 1, "demand_level": "LOW", "price_multiplier": 0.85 },
      { "hour": 7, "predicted_bookings": 3, "demand_level": "MODERATE", "price_multiplier": 1.0 },
      { "hour": 8, "predicted_bookings": 6, "demand_level": "HIGH", "price_multiplier": 1.15 },
      { "hour": 9, "predicted_bookings": 7, "demand_level": "HIGH", "price_multiplier": 1.15 },
      { "hour": 17, "predicted_bookings": 8, "demand_level": "PEAK", "price_multiplier": 1.3 },
      { "hour": 18, "predicted_bookings": 8, "demand_level": "PEAK", "price_multiplier": 1.3 },
      { "hour": 19, "predicted_bookings": 7, "demand_level": "HIGH", "price_multiplier": 1.15 },
      { "hour": 22, "predicted_bookings": 2, "demand_level": "LOW", "price_multiplier": 0.85 }
    ],
    "peak_hours": [17, 18],
    "best_hours_to_book": [6, 22, 23],
    "model_confidence": 0.82
  }
}
```

---

## 9. Reviews API

### 9.1 Submit Review

```
POST /stations/:station_id/reviews
Authorization: Bearer <access_token>
```

Only users with a `COMPLETED` booking at the station can submit a review (verified visitor check).

**Request:**
```json
{
  "booking_id": "uuid",
  "rating": 4,
  "comment": "Fast charger, good parking. Cafe nearby is a plus."
}
```

**Response 201:**
```json
{
  "success": true,
  "data": {
    "review_id": "uuid",
    "station_id": "uuid",
    "rating": 4,
    "comment": "Fast charger, good parking. Cafe nearby is a plus.",
    "created_at": "2026-05-13T15:32:00Z"
  }
}
```

---

### 9.2 Get Station Reviews

```
GET /stations/:station_id/reviews
Authorization: Bearer <access_token>
```

**Query Parameters:** `limit` (default 10), `offset` (default 0)

**Response 200:**
```json
{
  "success": true,
  "data": {
    "station_id": "uuid",
    "avg_rating": 4.3,
    "total_reviews": 47,
    "rating_breakdown": {
      "5": 21,
      "4": 15,
      "3": 7,
      "2": 3,
      "1": 1
    },
    "reviews": [
      {
        "id": "uuid",
        "user": { "name": "Arjun S.", "vehicle_type": "Tata Nexon EV" },
        "rating": 4,
        "comment": "Fast charger, good parking.",
        "created_at": "2026-05-13T15:32:00Z"
      }
    ]
  },
  "pagination": { "total": 47, "limit": 10, "offset": 0, "has_next": true, "has_prev": false }
}
```

---

## 10. Notifications API

### 10.1 Get User Notifications

```
GET /notifications
Authorization: Bearer <access_token>
```

**Query Parameters:** `unread_only` (bool, default false), `limit`, `offset`

**Response 200:**
```json
{
  "success": true,
  "data": {
    "notifications": [
      {
        "id": "uuid",
        "type": "BOOKING_CONFIRMED",
        "title": "✅ Slot Confirmed!",
        "body": "Your slot at Tata Power EZ Charge — DB Mall is confirmed.",
        "data": {
          "screen": "booking",
          "booking_id": "uuid"
        },
        "is_read": false,
        "created_at": "2026-05-13T07:31:45Z"
      }
    ],
    "unread_count": 2
  }
}
```

---

### 10.2 Mark Notifications as Read

```
PATCH /notifications/read
Authorization: Bearer <access_token>
```

**Request:**
```json
{
  "notification_ids": ["uuid1", "uuid2"]
}
```

Pass `"all": true` to mark all as read.

**Response 200:**
```json
{
  "success": true,
  "data": { "marked_read": 2 }
}
```

---

### 10.3 Register Push Token

```
POST /notifications/push-token
Authorization: Bearer <access_token>
```

**Request:**
```json
{
  "expo_push_token": "ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]"
}
```

**Response 200:**
```json
{
  "success": true,
  "data": { "message": "Push token registered successfully." }
}
```

---

## 11. Admin API

All admin endpoints require role `station_admin` or `super_admin`. Station admins are restricted to their own managed stations.

### 11.1 Create Station

```
POST /admin/stations
Authorization: Bearer <access_token>  (role: station_admin | super_admin)
```

**Request:**
```json
{
  "name": "Statiq EV Hub — Habibganj",
  "network": "STATIQ",
  "location": { "lat": 23.2282, "lng": 77.4383 },
  "address": {
    "line1": "Habibganj Railway Station, Platform Side",
    "line2": null,
    "city": "Bhopal",
    "state": "Madhya Pradesh",
    "pincode": "462001"
  },
  "operating_hours": {
    "open": "05:00",
    "close": "23:30",
    "days": [1, 2, 3, 4, 5, 6, 7]
  },
  "price_per_unit": 14.00,
  "price_per_hour": null,
  "amenities": ["parking", "restroom"],
  "slots": [
    { "slot_number": 1, "charger_type": "DC_FAST", "power_kw": 50.0 },
    { "slot_number": 2, "charger_type": "DC_FAST", "power_kw": 50.0 },
    { "slot_number": 3, "charger_type": "TYPE2", "power_kw": 22.0 },
    { "slot_number": 4, "charger_type": "BHARAT_AC", "power_kw": 3.3 }
  ]
}
```

**Response 201:** Full station object with generated IDs for station and all slots.

---

### 11.2 Update Station

```
PATCH /admin/stations/:id
Authorization: Bearer <access_token>  (role: station_admin | super_admin)
```

Partial update — only provided fields are changed.

**Request (example — update pricing):**
```json
{
  "price_per_unit": 16.00,
  "operating_hours": {
    "open": "06:00",
    "close": "22:00",
    "days": [1, 2, 3, 4, 5, 6, 7]
  }
}
```

---

### 11.3 Update Slot Status

```
PATCH /admin/stations/:station_id/slots/:slot_id
Authorization: Bearer <access_token>  (role: station_admin | super_admin)
```

Used to manually mark a slot offline (hardware fault) or bring it back online.

**Request:**
```json
{
  "status": "OFFLINE",
  "fault_code": "CONNECTOR_LOCK_FAILURE"
}
```

**Response 200:**
```json
{
  "success": true,
  "data": {
    "slot_id": "uuid",
    "status": "OFFLINE",
    "fault_code": "CONNECTOR_LOCK_FAILURE",
    "affected_bookings": [
      {
        "booking_id": "uuid",
        "user_phone": "+91987XXXXX10",
        "scheduled_start": "2026-05-13T14:00:00+05:30",
        "action": "notification_sent"
      }
    ]
  }
}
```

---

### 11.4 Analytics — Station Overview

```
GET /admin/analytics/overview
Authorization: Bearer <access_token>  (role: station_admin | super_admin)
```

**Query Parameters:** `station_id` (optional, station_admin sees own), `period` (`today`, `7d`, `30d`, `90d`)

**Response 200:**
```json
{
  "success": true,
  "data": {
    "period": "7d",
    "summary": {
      "total_bookings": 342,
      "completed_bookings": 298,
      "cancelled_bookings": 44,
      "total_revenue": 54360.00,
      "avg_utilization_percent": 67.4,
      "total_energy_dispensed_kwh": 2847.3
    },
    "daily_revenue": [
      { "date": "2026-05-07", "revenue": 7200.00, "bookings": 40 },
      { "date": "2026-05-08", "revenue": 8640.00, "bookings": 48 },
      { "date": "2026-05-09", "revenue": 9360.00, "bookings": 52 },
      { "date": "2026-05-10", "revenue": 6480.00, "bookings": 36 },
      { "date": "2026-05-11", "revenue": 5760.00, "bookings": 32 },
      { "date": "2026-05-12", "revenue": 9360.00, "bookings": 52 },
      { "date": "2026-05-13", "revenue": 7560.00, "bookings": 42 }
    ],
    "demand_heatmap": [
      { "day_of_week": 1, "hour": 8, "booking_count": 12 },
      { "day_of_week": 1, "hour": 17, "booking_count": 18 },
      { "day_of_week": 5, "hour": 18, "booking_count": 21 }
    ],
    "top_stations": [
      {
        "station_id": "uuid",
        "name": "Tata Power EZ Charge — DB Mall",
        "revenue": 21600.00,
        "utilization_percent": 82.1
      }
    ]
  }
}
```

---

### 11.5 Get All Bookings (Admin)

```
GET /admin/bookings
Authorization: Bearer <access_token>  (role: station_admin | super_admin)
```

**Query Parameters:** `station_id`, `status`, `date_from`, `date_to`, `limit`, `offset`

Returns full booking list with user details and payment status for admin view.

---

## 12. WebSocket Events

EVChargeFinder uses **Supabase Realtime** (built on Phoenix Channels over WebSocket) for live updates. The React Native client subscribes to channels using the Supabase JS SDK.

### 12.1 Channel: Station Slots

**Channel name:** `station:{station_id}:slots`
**Trigger:** Any `UPDATE` on the `slots` table for the given station

**Payload received by client:**
```json
{
  "eventType": "UPDATE",
  "schema": "public",
  "table": "slots",
  "old": {
    "id": "uuid",
    "status": "AVAILABLE"
  },
  "new": {
    "id": "uuid",
    "station_id": "uuid",
    "slot_number": 3,
    "charger_type": "CCS2",
    "power_kw": 50.0,
    "status": "BOOKED",
    "locked_until": null
  }
}
```

**Client action:** Update slot status in Zustand store → SlotGrid re-renders

---

### 12.2 Channel: Station Availability Count

**Channel name:** `station:{station_id}:count`
**Trigger:** Any `UPDATE` on the `stations` table (available_slots column changes via trigger)

**Payload received by client:**
```json
{
  "eventType": "UPDATE",
  "new": {
    "id": "uuid",
    "available_slots": 2,
    "total_slots": 8
  }
}
```

**Client action:** Update map pin color → green (>2), yellow (1), red (0)

---

### 12.3 Channel: User Bookings

**Channel name:** `bookings:{user_id}`
**Trigger:** `UPDATE` on `bookings` table for the user's bookings

**Payload received by client:**
```json
{
  "eventType": "UPDATE",
  "new": {
    "id": "uuid",
    "status": "CONFIRMED",
    "qr_code": "a3f9e2b1c4d5e6f7..."
  }
}
```

**Client action:** Navigate user to booking confirmation screen

---

### 12.4 Channel: Admin — All Stations

**Channel name:** `admin:all_stations`
**Filter:** Only accessible to tokens with `role IN (station_admin, super_admin)`

**Payload:** Broadcasts any slot or station status change across all managed stations — powers the live admin monitoring grid.

---

## 13. Rate Limits Reference

| Endpoint Group | Limit | Window | Strategy |
|---|---|---|---|
| POST /auth/otp/send | 3 requests | per phone per 10 min | Redis counter + TTL |
| POST /auth/otp/verify | 5 attempts | per phone per 10 min | Redis counter + lockout |
| GET /stations/nearby | 60 requests | per user per min | Redis sliding window |
| POST /bookings | 10 requests | per user per min | Redis sliding window |
| POST /payments/webhook | Unlimited | — | Razorpay IP whitelist only |
| All other endpoints | 100 requests | per user per min | Redis sliding window |
| Unauthenticated | 20 requests | per IP per min | Redis sliding window |

**Rate limit response headers:**
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1747123260
Retry-After: 47      ← Only on 429 responses
```

---

## 14. Status Code Reference

| Code | Meaning | When Used |
|---|---|---|
| `200 OK` | Success (read/update) | GET, PATCH operations |
| `201 Created` | Resource created | POST /bookings, POST /stations, POST /reviews |
| `204 No Content` | Success, no body | DELETE operations |
| `400 Bad Request` | Validation failure | Malformed request body, invalid params |
| `401 Unauthorized` | Auth failure | Missing/invalid/expired JWT, bad OTP |
| `403 Forbidden` | Authorization failure | Valid JWT but insufficient role |
| `404 Not Found` | Resource missing | Invalid station/booking/slot ID |
| `409 Conflict` | State conflict | Double booking, duplicate idempotency key |
| `422 Unprocessable` | Business logic failure | Payment signature invalid, unverifiable webhook |
| `429 Too Many Requests` | Rate limited | See rate limits table above |
| `500 Internal Server Error` | Unexpected error | Unhandled exception — always logged |
| `503 Service Unavailable` | Dependency down | Razorpay/Google Maps API unreachable |

---

*Document End — EVChargeFinder API Specification v1.0*

*Next Documents:*
- *DB_MIGRATIONS.md — Alembic migration files with step-by-step setup*
- *DEPLOYMENT.md — Railway + Vercel + Supabase production setup guide*
- *FRONTEND_ARCH.md — React Native component architecture + state management*
