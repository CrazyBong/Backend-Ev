# ⚡ EVChargeFinder Frontend API Map

This document outlines the core endpoints needed for the React Native App connection. Admin and IoT physical device webhooks have been excluded for clarity.

---

## 📦 Domain: auth

### `POST /v1/auth/otp/send`
> **Request Otp**

---

### `POST /v1/auth/otp/verify`
> **Confirm Otp**

---

### `POST /v1/auth/token/refresh`
> **Refresh Access Token**

---

### `DELETE /v1/auth/logout`
> **Logout**

- 🔐 **Auth Required**: Bearer Token (JWT)

---

### `GET /v1/auth/me`
> **Get Me**

- 🔐 **Auth Required**: Bearer Token (JWT)

---

## 📦 Domain: bookings

### `POST /v1/bookings`
> **Request Booking**

**Query Parameters:**

- 🔐 **Auth Required**: Bearer Token (JWT)

---

### `GET /v1/bookings`
> **List User Bookings**

- 🔐 **Auth Required**: Bearer Token (JWT)

---

### `DELETE /v1/bookings/{booking_id}`
> **Cancel Booking**

**Query Parameters:**

- 🔐 **Auth Required**: Bearer Token (JWT)

---

## 📦 Domain: demand

### `GET /v1/demand/predict/{station_id}`
> **24-hour demand forecast (ML or WMA)**

**Query Parameters:**

- 🔐 **Auth Required**: Bearer Token (JWT)

---

### `GET /v1/demand/pricing/{station_id}`
> **Current surge pricing for a station**

**Query Parameters:**

- 🔐 **Auth Required**: Bearer Token (JWT)

---

### `POST /v1/demand/train/{station_id}`
> **Trigger RF model training for a station (admin only)**

**Query Parameters:**

- 🔐 **Auth Required**: Bearer Token (JWT)

---

## 📦 Domain: notifications

### `GET /v1/notifications`
> **List Notifications**

- 🔐 **Auth Required**: Bearer Token (JWT)

---

### `POST /v1/notifications/{notification_id}/read`
> **Mark Notification Read**

**Query Parameters:**

- 🔐 **Auth Required**: Bearer Token (JWT)

---

### `POST /v1/notifications/read-all`
> **Mark All Notifications Read**

- 🔐 **Auth Required**: Bearer Token (JWT)

---

## 📦 Domain: payments

### `POST /v1/payments/verify`
> **Verify Payment**

- 🔐 **Auth Required**: Bearer Token (JWT)

---

### `POST /v1/payments/webhook`
> **Razorpay Webhook**

---

## 📦 Domain: reviews

### `POST /v1/reviews`
> **Post Review**

- 🔐 **Auth Required**: Bearer Token (JWT)

---

### `GET /v1/reviews/stations/{station_id}`
> **Get Reviews**

**Query Parameters:**
- `limit` (Optional)
- `offset` (Optional)

---

## 📦 Domain: routes

### `POST /v1/routes/plan`
> **Plan Route**

---

## 📦 Domain: slots

### `GET /v1/slots/stations/{station_id}`
> **List Station Slots**

**Query Parameters:**

- 🔐 **Auth Required**: Bearer Token (JWT)

---

### `GET /v1/slots/{slot_id}`
> **Get Slot Detail**

**Query Parameters:**

- 🔐 **Auth Required**: Bearer Token (JWT)

---

## 📦 Domain: stations

### `GET /v1/stations/nearby`
> **Nearby Stations**

**Query Parameters:**
- `lat` (Required)
- `lng` (Required)
- `radius_km` (Optional)
- `charger_type` (Optional)
- `available_only` (Optional)
- `limit` (Optional)
- `offset` (Optional)

- 🔐 **Auth Required**: Bearer Token (JWT)

---

### `GET /v1/stations/{station_id}`
> **Station Detail**

**Query Parameters:**

- 🔐 **Auth Required**: Bearer Token (JWT)

---

### `PATCH /v1/stations/{station_id}`
> **Update Station**

**Query Parameters:**

- 🔐 **Auth Required**: Bearer Token (JWT)

---

### `POST /v1/stations`
> **Create Station**

- 🔐 **Auth Required**: Bearer Token (JWT)

---

