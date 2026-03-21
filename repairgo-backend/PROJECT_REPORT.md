# RepairGo Backend - Complete Project Report

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Technology Stack](#2-technology-stack)
3. [System Architecture](#3-system-architecture)
4. [Database Schema](#4-database-schema)
5. [Feature Modules](#5-feature-modules)
6. [ML Models Integration](#6-ml-models-integration)
7. [API Endpoints Reference](#7-api-endpoints-reference)
8. [Security Features](#8-security-features)
9. [Background Services](#9-background-services)
10. [Complete Workflow Diagrams](#10-complete-workflow-diagrams)

---

## 1. Project Overview

**RepairGo** is a home repair service platform that connects customers with skilled technicians for on-demand repair services. The backend is built with FastAPI and MongoDB, featuring ML-powered technician matching, dynamic pricing, and fraud detection.

### Core Business Flow

```
Customer → Creates Service Request → System Assigns Best Technician →
Technician Travels & Completes Job → Customer Rates → Payment Processed
```

### Key Capabilities

- User registration and JWT authentication
- Role-based access control (Customer, Technician, Admin)
- Smart technician matching with ML prediction
- Dynamic pricing with demand-based surge
- Real-time job status tracking
- Fraud detection and prevention
- Background job monitoring

---

## 2. Technology Stack

| Component  | Technology       | Purpose                     |
| ---------- | ---------------- | --------------------------- |
| Framework  | FastAPI          | REST API endpoints          |
| Database   | MongoDB          | Document storage            |
| Auth       | JWT (PyJWT)      | Token-based authentication  |
| Password   | bcrypt (passlib) | Password hashing            |
| ML         | scikit-learn     | Machine learning models     |
| Validation | Pydantic         | Request/response validation |
| Logging    | Python logging   | Application logs            |

### File Structure

```
repairgo-backend/
├── venv/
│   ├── main.py              # FastAPI application entry + WebSocket
│   └── database.py          # MongoDB connection
├── models/
│   ├── user_model.py        # User Pydantic models
│   ├── technician_model.py  # Technician Pydantic models
│   ├── service_model.py     # Service + Payment Pydantic models
│   └── category_model.py    # Category Pydantic models
├── routes/
│   ├── user_routes.py       # User endpoints
│   ├── technician_routes.py # Technician endpoints
│   ├── service_routes.py    # Service + Payment endpoints
│   ├── admin_routes.py      # Admin + Deactivation endpoints
│   └── ml_routes.py         # ML + Model Registry endpoints
├── utils/
│   ├── auth_utils.py        # JWT authentication
│   ├── jwt_utils.py         # Token generation/validation
│   ├── password_utils.py    # Password hashing
│   ├── rate_limit.py        # Login rate limiting
│   ├── technician_selection.py  # Scoring algorithm + Caching
│   ├── pricing.py           # Price calculation
│   ├── notification_utils.py    # Event notifications + WebSocket push
│   ├── websocket_manager.py # Real-time WebSocket connections
│   ├── reassignment_utils.py    # Stale job reassignment
│   ├── fraud_utils.py       # Rule-based fraud detection
│   ├── background_job_monitor.py # Job health tracking
│   ├── logger.py            # Logging utilities
│   ├── response_utils.py    # API response format
│   └── exception_handler.py # Global error handling
└── ml/
    ├── training_pipeline.py     # Reliability model training
    ├── predictor.py             # Reliability prediction + Explainability
    ├── demand_forecasting.py    # Demand model training
    ├── demand_predictor.py      # Demand prediction
    ├── fraud_detection.py       # Fraud model training
    ├── fraud_predictor.py       # Fraud prediction
    ├── model_registry.py        # ML model versioning & metrics
    ├── ml_utils.py              # ML safeguards
    └── saved_models/            # Serialized models
```

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                    │
│                    (Mobile App / Web Frontend)                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           API GATEWAY (FastAPI)                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     Exception Handler                                │    │
│  │        Converts all exceptions to standard JSON responses            │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │  User    │ │Technician│ │ Service  │ │  Admin   │ │    ML    │          │
│  │ Routes   │ │  Routes  │ │  Routes  │ │  Routes  │ │  Routes  │          │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘          │
│       │            │            │            │            │                  │
│       └────────────┴────────────┴────────────┴────────────┘                  │
│                                    │                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     Authentication Layer                             │    │
│  │         JWT Token Validation + Role-Based Access Control             │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
┌───────────────────────┐ ┌───────────────────┐ ┌───────────────────────────┐
│   BUSINESS LOGIC      │ │    ML LAYER       │ │   BACKGROUND SERVICES     │
│                       │ │                   │ │                           │
│ ├── Pricing Engine    │ │ ├── Reliability   │ │ ├── Stale Job Reassign    │
│ ├── Tech Selection    │ │ │    Predictor    │ │ │    (every 60s)          │
│ ├── Fraud Detection   │ │ ├── Demand        │ │ ├── Job Health Monitor    │
│ └── Notifications     │ │ │    Predictor    │ │ └── Metrics Collector     │
│                       │ │ └── Fraud         │ │                           │
│                       │ │      Detector     │ │                           │
└───────────────────────┘ └───────────────────┘ └───────────────────────────┘
                    │               │               │
                    └───────────────┼───────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              MONGODB DATABASE                                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │  users   │ │technicians│ │ services │ │categories│ │fraud_flags│          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐                        │
│  │ feedback │ │notifications││ payments │ │ml_models │                        │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Database Schema

### 4.1 Users Collection

```javascript
{
  "_id": ObjectId,
  "name": String,
  "email": String (unique),
  "password": String (bcrypt hash),
  "role": "customer" | "technician" | "admin",
  "is_active": Boolean
}
```

### 4.2 Technicians Collection

```javascript
{
  "_id": ObjectId,
  "name": String,
  "email": String (unique),
  "skills": ["plumbing", "electrical", ...],
  "experience_years": Number,
  "availability": Boolean,
  "workload": Number,           // Current active jobs
  "latitude": Number,
  "longitude": Number,
  "rating": Number (0-5),
  "completed_jobs": Number,
  "cancelled_jobs": Number,
  "is_active": Boolean
}
```

### 4.3 Services Collection

```javascript
{
  "_id": ObjectId,
  "category": String,
  "description": String,
  "location": {
    "latitude": Number,
    "longitude": Number
  },
  "urgency": "low" | "medium" | "high",
  "status": "pending" | "assigned" | "on_the_way" |
            "in_progress" | "completed" | "rated" | "cancelled",
  "customer_id": String,
  "technician_id": String,
  "estimated_price": Number,
  "final_price": Number,
  "rating": Number,
  "eta_minutes": Number,
  "created_at": DateTime,
  "assigned_at": DateTime,
  "updated_at": DateTime,
  "assignment_history": [String],  // Previous technician IDs
  "is_active": Boolean
}
```

### 4.4 Categories Collection

```javascript
{
  "_id": ObjectId,
  "name": String,
  "base_price": Number,
  "travel_rate": Number,
  "urgency_addon": {
    "low": Number,
    "medium": Number,
    "high": Number
  }
}
```

### 4.5 Fraud Flags Collection

```javascript
{
  "_id": ObjectId,
  "entity_id": String (unique),
  "entity_type": "technician" | "service",
  "reason": String,
  "anomaly_score": Number,
  "is_anomaly": Boolean,
  "confidence": Number,
  "top_contributing_features": Array,
  "prediction_source": "model" | "rule_based",
  "flagged_at": DateTime,
  "status": "pending_review" | "cleared" | "confirmed"
}
```

### 4.6 Notifications Collection

```javascript
{
  "_id": ObjectId,
  "recipient_id": String,
  "event_type": "assignment" | "status_update" |
                "cancellation" | "reassignment" | "rating",
  "message": String,
  "related_id": String,
  "context": Object,
  "created_at": DateTime,
  "read": Boolean
}
```

---

## 5. Feature Modules

### 5.1 User Management

**File:** `routes/user_routes.py`, `models/user_model.py`

| Feature    | Endpoint       | Method | Auth  |
| ---------- | -------------- | ------ | ----- |
| Register   | `/register`    | POST   | None  |
| Login      | `/login`       | POST   | None  |
| List Users | `/admin/users` | GET    | Admin |

**Registration Flow:**

```
Input: name, email, password, role
    │
    ▼
┌─────────────────────────────┐
│ Validate with Pydantic      │
│ - name not empty            │
│ - email valid format        │
│ - password min 6 chars      │
│ - role in allowed values    │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ Hash password with bcrypt   │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ Insert into MongoDB         │
│ (email unique index)        │
└──────────────┬──────────────┘
               │
               ▼
Return: success message
```

**Login Flow:**

```
Input: email, password
    │
    ▼
┌─────────────────────────────┐
│ Check rate limit (5/5min)   │
│ If exceeded: 429 error      │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ Find user by email          │
│ Verify password with bcrypt │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ Generate JWT token          │
│ - sub: user_id              │
│ - email: user email         │
│ - role: user role           │
│ - exp: now + 60 minutes     │
└──────────────┬──────────────┘
               │
               ▼
Return: { access_token, token_type, role }
```

### 5.2 Technician Management

**File:** `routes/technician_routes.py`, `models/technician_model.py`

| Feature         | Endpoint                | Method | Auth       |
| --------------- | ----------------------- | ------ | ---------- |
| Register        | `/register-technician`  | POST   | None       |
| Update Location | `/technicians/location` | PATCH  | Technician |

**Technician Data Model:**

```
- Skills: Array of service categories they can handle
- Experience Years: Years of professional experience
- Availability: Whether accepting new jobs
- Workload: Current number of active jobs
- Location: Real-time GPS coordinates
- Rating: Average customer rating (0-5)
- Completed Jobs: Historical count
- Cancelled Jobs: Historical count (affects scoring)
```

### 5.3 Service Request Management

**File:** `routes/service_routes.py`, `models/service_model.py`

| Feature           | Endpoint                | Method | Auth       |
| ----------------- | ----------------------- | ------ | ---------- |
| Create Request    | `/services`             | POST   | Customer   |
| Get Estimate      | `/services/estimate`    | POST   | Customer   |
| Update Status     | `/services/{id}/status` | PATCH  | Technician |
| Assign Technician | `/services/{id}/assign` | POST   | Admin      |
| Rate Service      | `/services/{id}/rate`   | POST   | Customer   |
| Cancel Service    | `/services/{id}/cancel` | POST   | Technician |

**Service Status Flow:**

```
┌──────────┐    ┌──────────┐    ┌───────────┐    ┌─────────────┐
│ PENDING  │───►│ ASSIGNED │───►│ ON_THE_WAY│───►│ IN_PROGRESS │
└──────────┘    └──────────┘    └───────────┘    └──────┬──────┘
                     │                                   │
                     │                                   ▼
               ┌─────┴─────┐                      ┌───────────┐
               │ CANCELLED │                      │ COMPLETED │
               └───────────┘                      └─────┬─────┘
                                                        │
                                                        ▼
                                                  ┌───────────┐
                                                  │   RATED   │
                                                  └───────────┘
```

### 5.4 Pricing Engine

**File:** `utils/pricing.py`

**Price Formula:**

```
Final Price = (Base Price + Travel Cost + Urgency Addon) × Demand Multiplier

Where:
- Base Price = Category-specific base rate (e.g., plumbing: $60)
- Travel Cost = Distance (km) × $2.00/km
- Urgency Addon = Low: $0, Medium: $10, High: $25
- Demand Multiplier = ML-predicted surge (0.9, 1.0, or 1.2)
```

**Pricing Flow:**

```
┌─────────────────────────────────────────────────────────────┐
│ estimate_price(category, urgency, distance, active_requests) │
└───────────────────────────────┬─────────────────────────────┘
                                │
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
         ┌───────────┐   ┌───────────┐   ┌───────────────┐
         │Base Price │   │Travel Cost│   │Urgency Addon  │
         │from DB    │   │dist×$2/km │   │from lookup    │
         └─────┬─────┘   └─────┬─────┘   └───────┬───────┘
               │               │                 │
               └───────────────┴─────────────────┘
                               │
                               ▼
                ┌─────────────────────────────────┐
                │ get_demand_multiplier()         │
                │                                 │
                │ ┌─────────────────────────────┐ │
                │ │ Try ML Demand Prediction    │ │
                │ │   ├── Model available?      │ │
                │ │   │     ├── Yes: predict()  │ │
                │ │   │     └── No: fallback    │ │
                │ │   └── Return multiplier     │ │
                │ └─────────────────────────────┘ │
                └────────────────┬────────────────┘
                                 │
                                 ▼
                ┌─────────────────────────────────┐
                │ final = subtotal × multiplier   │
                └────────────────┬────────────────┘
                                 │
                                 ▼
                Return: {
                  base_price, travel_cost, urgency_addon,
                  demand_multiplier, demand_level, final_price
                }
```

### 5.5 Technician Selection Algorithm

**File:** `utils/technician_selection.py`

**Scoring Formula:**

```
Score = (0.30 × SkillMatch) + (0.25 × Proximity) + (0.20 × Availability) +
        (0.20 × PredictedSuccessProbability) + (0.05 × WorkloadScore)
```

| Component         | Weight | Calculation                         |
| ----------------- | ------ | ----------------------------------- |
| Skill Match       | 30%    | 1.0 if category in skills, else 0.0 |
| Proximity         | 25%    | 1.0 - (distance_km / 50.0)          |
| Availability      | 20%    | 1.0 if available, else 0.0          |
| Predicted Success | 20%    | ML model output (0-1)               |
| Workload          | 5%     | 1.0 - (current_workload / 10)       |

**Selection Flow:**

```
┌─────────────────────────────────────────────────────────────┐
│ select_best_technician(service, technicians, exclude_ids)   │
└───────────────────────────────┬─────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│ For each technician:                                         │
│   1. Check skill match (category in skills?)                 │
│   2. Calculate distance (Haversine formula)                  │
│   3. Check availability status                               │
│   4. Get ML predicted success probability ◄── ML MODEL       │
│   5. Calculate workload score                                │
│   6. Compute weighted score                                  │
└───────────────────────────────┬─────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│ Sort by score (descending)                                   │
│ Return top technician                                        │
└─────────────────────────────────────────────────────────────┘
```

### 5.6 Notification System

**File:** `utils/notification_utils.py`

| Event Type    | Trigger              | Recipient      |
| ------------- | -------------------- | -------------- |
| ASSIGNMENT    | Job assigned         | Technician     |
| STATUS_UPDATE | Status changed       | Customer       |
| CANCELLATION  | Job cancelled        | Customer       |
| REASSIGNMENT  | Stale job reassigned | New Technician |
| RATING        | Rating submitted     | Technician     |

### 5.7 Admin Dashboard

**File:** `routes/admin_routes.py`

| Feature           | Endpoint                        | Description                   |
| ----------------- | ------------------------------- | ----------------------------- |
| List Users        | `/admin/users`                  | All active users              |
| List Technicians  | `/admin/technicians`            | With performance scores       |
| List Requests     | `/admin/requests`               | All service requests          |
| Revenue Stats     | `/admin/revenue`                | Total, by category, by month  |
| Manage Categories | `/admin/categories`             | Create/update categories      |
| Reassign Stale    | `/admin/reassign-stale`         | Manual stale job reassignment |
| Fraud Check       | `/admin/fraud/check`            | ML/rule-based fraud scan      |
| Job Health        | `/admin/health/background-jobs` | Background job status         |

---

## 6. ML Models Integration

### 6.1 Technician Reliability Prediction

**Files:** `ml/training_pipeline.py`, `ml/predictor.py`

**Algorithm:** Random Forest Classifier

**Features (6):**
| Feature | Description | Source |
|---------|-------------|--------|
| avg_rating | Average customer rating | technicians.rating |
| cancellation_rate | Cancelled/Total jobs | Calculated |
| avg_response_time | Historical response time | Derived |
| completed_jobs | Total completed jobs | technicians.completed_jobs |
| current_workload | Active job count | technicians.workload |
| distance_to_customer | Distance in km | Haversine calculation |

**Output:** Success probability (0.0 - 1.0)

**Integration Point:** `utils/technician_selection.py` → `get_predicted_success_probability()`

**Fallback Logic:**

```python
if model_available:
    return model.predict_proba(features)[0, 1]
else:
    # Rule-based fallback
    return (
        0.30 * rating_score +
        0.25 * cancel_score +
        0.15 * response_score +
        0.10 * experience_score +
        0.10 * workload_score +
        0.10 * distance_score
    )
```

### 6.2 Demand Forecasting

**Files:** `ml/demand_forecasting.py`, `ml/demand_predictor.py`

**Algorithm:** Random Forest Regressor

**Features (7 - Cyclical Encoded):**
| Feature | Description |
|---------|-------------|
| hour_sin | sin(2π × hour/24) |
| hour_cos | cos(2π × hour/24) |
| day_sin | sin(2π × weekday/7) |
| day_cos | cos(2π × weekday/7) |
| is_weekend | 1.0 if Saturday/Sunday |
| month_sin | sin(2π × (month-1)/12) |
| month_cos | cos(2π × (month-1)/12) |

**Output:** Predicted request count per hour

**Demand Levels:**
| Predicted Count | Level | Multiplier |
|-----------------|-------|------------|
| < 5 | Low | 0.9× |
| 5-15 | Normal | 1.0× |
| > 15 | High | 1.2× |

**Cache System:** 10-minute TTL to reduce computation

**Integration Point:** `utils/pricing.py` → `get_demand_multiplier()`

**Fallback Logic:**

```python
if model_available:
    return model.predict(features)
else:
    # Time-based pattern fallback
    base = 8 if is_weekend else 10
    if 8 <= hour <= 11: return base * 1.5   # Morning peak
    if 14 <= hour <= 18: return base * 1.3  # Afternoon peak
    if hour < 6 or hour > 22: return base * 0.5  # Night
    return base
```

### 6.3 Fraud Detection

**Files:** `ml/fraud_detection.py`, `ml/fraud_predictor.py`

**Algorithm:** Isolation Forest (unsupervised anomaly detection)

**Features (6 for technicians):**
| Feature | Description | Fraud Signal |
|---------|-------------|--------------|
| cancellation_rate | Cancelled/Total | High = suspicious |
| price_deviation_avg | Avg price deviation | High = suspicious |
| job_frequency | Jobs per day | Very high = suspicious |
| rating_variation | Std dev of ratings | High = suspicious |
| completion_time_variance | Time variance | High = suspicious |
| avg_rating | Average rating | Very low = suspicious |

**Output:**

- `anomaly_score`: Negative values = more anomalous
- `is_anomaly`: Boolean flag
- `confidence`: 0.0 - 1.0
- `top_contributing_features`: Explainability

**Threshold:** anomaly_score < -0.3 ⟹ flagged

**Integration Points:**

- `routes/admin_routes.py` → `admin_fraud_check()`
- `routes/ml_routes.py` → Dedicated fraud endpoints

**Fallback Logic:**

```python
if model_available:
    return model.decision_function(features)
else:
    # Rule-based thresholds
    risk = 0.0
    if cancellation_rate > 0.3: risk += 0.4
    if price_deviation > 0.3: risk += 0.3
    if rating < 2.0: risk += 0.2
    return -risk  # Negative = anomalous
```

### 6.4 ML Safeguards

**File:** `ml/ml_utils.py`

| Safeguard          | Value       | Purpose          |
| ------------------ | ----------- | ---------------- |
| PREDICTION_TIMEOUT | 5 seconds   | Prevent hanging  |
| TRAINING_TIMEOUT   | 300 seconds | Long operations  |
| SCAN_TIMEOUT       | 60 seconds  | Batch operations |

**All predictions include:**

- `latency_ms`: Execution time
- `prediction_source`: model/fallback/fallback_timeout/fallback_error
- `model_available`: Boolean

---

## 7. API Endpoints Reference

### 7.1 User Endpoints (`/`)

| Endpoint    | Method | Auth | Description       |
| ----------- | ------ | ---- | ----------------- |
| `/register` | POST   | None | Register new user |
| `/login`    | POST   | None | Login and get JWT |

### 7.2 Technician Endpoints (`/`)

| Endpoint                | Method | Auth       | Description         |
| ----------------------- | ------ | ---------- | ------------------- |
| `/register-technician`  | POST   | None       | Register technician |
| `/technicians/location` | PATCH  | Technician | Update GPS          |

### 7.3 Service Endpoints (`/services`)

| Endpoint                | Method | Auth       | Description        |
| ----------------------- | ------ | ---------- | ------------------ |
| `/services`             | POST   | Customer   | Create request     |
| `/services/estimate`    | POST   | Customer   | Get price estimate |
| `/services/{id}/status` | PATCH  | Technician | Update status      |
| `/services/{id}/assign` | POST   | Admin      | Auto-assign tech   |
| `/services/{id}/rate`   | POST   | Customer   | Submit rating      |
| `/services/{id}/cancel` | POST   | Technician | Cancel job         |

### 7.4 Admin Endpoints (`/admin`)

| Endpoint                        | Method | Auth  | Description      |
| ------------------------------- | ------ | ----- | ---------------- |
| `/admin/users`                  | GET    | Admin | List all users   |
| `/admin/technicians`            | GET    | Admin | List with scores |
| `/admin/requests`               | GET    | Admin | List requests    |
| `/admin/jobs`                   | GET    | Admin | List jobs        |
| `/admin/revenue`                | GET    | Admin | Revenue stats    |
| `/admin/categories`             | POST   | Admin | Upsert category  |
| `/admin/reassign-stale`         | POST   | Admin | Manual reassign  |
| `/admin/fraud/check`            | POST   | Admin | Run fraud scan   |
| `/admin/health/background-jobs` | GET    | Admin | Job health       |

### 7.5 ML Endpoints (`/ml`)

**Reliability:**
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/ml/predict-reliability` | POST | Admin/Tech | Predict success |
| `/ml/model-status` | GET | Admin | Model info |
| `/ml/train` | POST | Admin | Train model |
| `/ml/reload-model` | POST | Admin | Reload from disk |
| `/ml/train-and-reload` | POST | Admin | Combined |

**Demand:**
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/ml/predict-demand` | POST | Admin/Cust | Predict demand |
| `/ml/demand-model-status` | GET | Admin | Model info |
| `/ml/train-demand` | POST | Admin | Train model |
| `/ml/reload-demand-model` | POST | Admin | Reload |
| `/ml/demand-forecast` | GET | Admin | N-hour forecast |

**Fraud:**
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/ml/fraud-score/{type}/{id}` | GET | Admin | Get fraud score |
| `/ml/fraud-model-status` | GET | Admin | Model info |
| `/ml/train-fraud` | POST | Admin | Train model |
| `/ml/fraud-scan` | POST | Admin | Scan all entities |
| `/ml/fraud-flags` | GET | Admin | Get flagged |
| `/ml/fraud-flags/{id}/status` | PATCH | Admin | Update status |

---

## 8. Security Features

### 8.1 Authentication

**JWT Token Structure:**

```json
{
  "sub": "user_id",
  "email": "user@example.com",
  "role": "customer|technician|admin",
  "exp": 1740391200
}
```

**Configuration:**

- Secret: `JWT_SECRET` env variable
- Algorithm: HS256
- Expiration: 60 minutes

### 8.2 Role-Based Access Control

```python
@router.get("/admin/users")
def list_users(user=Depends(require_roles("admin"))):
    # Only admins can access
```

**Roles:**
| Role | Permissions |
|------|-------------|
| customer | Create requests, rate, view own data |
| technician | Update status, cancel, view assigned |
| admin | All operations, fraud checks, ML training |

### 8.3 Rate Limiting

**Login Protection:**

- Max 5 attempts per IP per 5 minutes
- Returns 429 Too Many Requests if exceeded
- Resets on successful login

### 8.4 Password Security

- Hashing: bcrypt with auto-salt
- Minimum length: 6 characters
- No plain text storage

### 8.5 Data Validation

- All inputs validated with Pydantic models
- Email format validation
- Coordinate bounds checking (-90/90, -180/180)
- Rating bounds (1-5)
- Status transition validation

---

## 9. Background Services

### 9.1 Stale Job Reassignment

**File:** `utils/reassignment_utils.py`

**Logic:**

```
Every 60 seconds:
  1. Find jobs with status="assigned" AND assigned_at > 5 minutes ago
  2. For each stale job:
     a. Find available technicians (excluding current)
     b. Use ML-powered scoring to select best
     c. Update assignment
     d. Notify new technician
  3. Log metrics
```

**Monitoring Endpoint:** `/admin/health/background-jobs`

### 9.2 Job Health Monitor

**File:** `utils/background_job_monitor.py`

**Tracked Metrics:**

```json
{
  "job_name": "reassignment_stale_jobs",
  "status": "completed",
  "last_execution": "2026-02-24T07:00:00",
  "next_execution": "2026-02-24T07:01:00",
  "execution_count": 150,
  "success_count": 148,
  "failure_count": 2,
  "last_error": null,
  "metrics": {
    "reassigned": 3,
    "attempted": 5,
    "execution_time_ms": 245
  },
  "health": "healthy"
}
```

---

## 10. Complete Workflow Diagrams

### 10.1 Customer Journey

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          CUSTOMER WORKFLOW                                   │
└─────────────────────────────────────────────────────────────────────────────┘

Customer                    Backend                         Database
   │                           │                               │
   │──POST /register──────────►│                               │
   │                           │──hash password───────────────►│
   │                           │◄─────────────────────────────│
   │◄──success────────────────│                               │
   │                           │                               │
   │──POST /login─────────────►│                               │
   │                           │◄──verify password────────────│
   │◄──JWT token──────────────│                               │
   │                           │                               │
   │──POST /services/estimate─►│                               │
   │                           │──get technicians─────────────►│
   │                           │──get active requests─────────►│
   │                           │                               │
   │                           │ ┌─────────────────────────┐   │
   │                           │ │ ML Demand Prediction    │   │
   │                           │ │ - predict demand level  │   │
   │                           │ │ - get multiplier        │   │
   │                           │ └─────────────────────────┘   │
   │                           │                               │
   │◄──price estimate─────────│                               │
   │                           │                               │
   │──POST /services──────────►│                               │
   │                           │──create service request──────►│
   │◄──service created────────│                               │
   │                           │                               │
   │                           │     [ADMIN ASSIGNS]           │
   │                           │                               │
   │◄──notification: assigned─│◄──push notification───────────│
   │                           │                               │
   │◄──notification: status───│◄──status updates──────────────│
   │                           │                               │
   │──POST /rate──────────────►│                               │
   │                           │──update tech rating──────────►│
   │                           │──mark service rated──────────►│
   │◄──rating submitted───────│                               │
```

### 10.2 Technician Assignment Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      TECHNICIAN ASSIGNMENT WORKFLOW                          │
└─────────────────────────────────────────────────────────────────────────────┘

Admin                       Backend                      ML Layer
  │                            │                            │
  │──POST /services/{id}/assign─►│                            │
  │                            │──get service details───────►│
  │                            │◄──service data─────────────│
  │                            │                            │
  │                            │──find available techs──────►│
  │                            │◄──technician list──────────│
  │                            │                            │
  │                            │    FOR EACH TECHNICIAN:    │
  │                            │ ┌──────────────────────────┐│
  │                            │ │1. Calculate skill match  ││
  │                            │ │2. Calculate distance     ││
  │                            │ │3. Check availability     ││
  │                            │ │                          ││
  │                            │ │4. ML Reliability Predict─┼──►predict_reliability()
  │                            │ │   └── success_probability││◄──probability
  │                            │ │                          ││
  │                            │ │5. Calculate workload score││
  │                            │ │6. Compute weighted total  ││
  │                            │ └──────────────────────────┘│
  │                            │                            │
  │                            │──select highest scorer─────│
  │                            │──update service──────────────►│
  │                            │──increment tech workload────►│
  │                            │──notify technician──────────►│
  │                            │                            │
  │◄──assignment details──────│                            │
  │   (tech_id, score, eta)   │                            │
```

### 10.3 Fraud Detection Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        FRAUD DETECTION WORKFLOW                              │
└─────────────────────────────────────────────────────────────────────────────┘

Admin                       Backend                      ML Layer
  │                            │                            │
  │──POST /admin/fraud/check──►│                            │
  │                            │                            │
  │                            │──check model status────────►│
  │                            │◄──model available: true────│
  │                            │                            │
  │                            │    FOR EACH TECHNICIAN:    │
  │                            │ ┌──────────────────────────┐│
  │                            │ │1. Extract features       ││
  │                            │ │   - cancellation_rate    ││
  │                            │ │   - price_deviation_avg  ││
  │                            │ │   - job_frequency        ││
  │                            │ │   - rating_variation     ││
  │                            │ │   - completion_variance  ││
  │                            │ │   - avg_rating           ││
  │                            │ │                          ││
  │                            │ │2. Isolation Forest───────┼──►decision_function()
  │                            │ │   └── anomaly_score      ││◄──score
  │                            │ │                          ││
  │                            │ │3. Calculate contributions ││
  │                            │ │4. If anomaly: flag       ││
  │                            │ └──────────────────────────┘│
  │                            │                            │
  │                            │    FOR EACH SERVICE:       │
  │                            │    [Similar process]       │
  │                            │                            │
  │                            │──store fraud flags─────────►│
  │                            │                            │
  │◄──scan results────────────│                            │
  │   {technicians_flagged,   │                            │
  │    services_flagged,      │                            │
  │    newly_flagged[]}       │                            │
```

### 10.4 Background Job Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     BACKGROUND JOB WORKFLOW (Every 60s)                      │
└─────────────────────────────────────────────────────────────────────────────┘

Background Task              Backend                      Database
     │                          │                            │
     │──start execution────────►│                            │
     │                          │                            │
     │                          │──find stale jobs───────────►│
     │                          │  (assigned > 5 min ago)    │
     │                          │◄──stale jobs list──────────│
     │                          │                            │
     │                          │    FOR EACH STALE JOB:     │
     │                          │ ┌──────────────────────────┐│
     │                          │ │1. Get available techs   ││
     │                          │ │   (exclude current)     ││
     │                          │ │                         ││
     │                          │ │2. ML-powered selection  ││
     │                          │ │   (same as assignment)  ││
     │                          │ │                         ││
     │                          │ │3. Update assignment     ││
     │                          │ │4. Push assignment_history││
     │                          │ │5. Notify new tech       ││
     │                          │ └──────────────────────────┘│
     │                          │                            │
     │◄──execution metrics─────│                            │
     │   {reassigned, attempted}│                            │
     │                          │                            │
     │──sleep 60 seconds───────│                            │
     │                          │                            │
     └──────────[REPEAT]────────┘                            │
```

---

## 11. Production Enhancements

### 11.1 Payment System Integration

**Files:** `routes/service_routes.py`, `models/service_model.py`, `database.py`

**Payment Status Flow:**

```
pending → paid/failed → refunded
```

**New Endpoints:**
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/services/{id}/pay` | POST | Customer | Process payment |
| `/services/{id}/refund` | POST | Admin | Process refund |

**New Service Fields:**

```javascript
{
  "payment_status": "pending" | "paid" | "failed" | "refunded",
  "payment_id": String,
  "paid_at": DateTime,
  "refund_id": String,
  "refund_amount": Number
}
```

**New Payments Collection:**

```javascript
{
  "_id": ObjectId,
  "payment_id": String,
  "service_id": String,
  "customer_id": String,
  "amount": Number,
  "payment_method": "card" | "cash" | "wallet",
  "status": "completed" | "refunded",
  "created_at": DateTime
}
```

---

### 11.2 Real-Time Communication (WebSocket)

**Files:** `utils/websocket_manager.py`, `venv/main.py`

**WebSocket Endpoint:**

```
ws://host/ws/notifications/{user_id}?token=JWT_TOKEN
```

**Features:**

- Per-user connection management (multi-device support)
- Message queuing for offline users
- Automatic push on notification creation
- Connection statistics monitoring

**Message Format:**

```json
{
  "type": "notification",
  "event_type": "assignment|status_update|payment|...",
  "message": "...",
  "related_id": "service_id",
  "context": {...},
  "timestamp": "ISO datetime"
}
```

**Monitoring Endpoint:**
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ws/stats` | GET | WebSocket connection statistics |

---

### 11.3 ML Model Registry & Versioning

**File:** `ml/model_registry.py`

**New Collection: ml_models**

```javascript
{
  "_id": ObjectId,
  "model_name": "reliability_rf" | "demand_rf" | "fraud_if",
  "model_type": "RandomForestClassifier",
  "version": "1.0.3",
  "version_number": 3,
  "content_hash": String,
  "accuracy": 0.87,
  "validation_score": 0.85,
  "feature_count": 6,
  "feature_names": [...],
  "training_samples": 400,
  "hyperparameters": {...},
  "training_duration_seconds": 2.5,
  "trained_at": DateTime,
  "deployed_at": DateTime,
  "is_active": Boolean,
  "notes": String
}
```

**New Endpoints:**
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ml/models` | GET | Get all models status |
| `/ml/models/{name}/history` | GET | Get training history |
| `/ml/models/{name}/active` | GET | Get deployed version |
| `/ml/models/{name}/deploy` | POST | Deploy specific version |

**Auto-Registration:** Models are automatically registered and deployed after training.

---

### 11.4 Reliability Model Explainability

**File:** `ml/predictor.py`

**Enhanced Prediction Response:**

```json
{
  "success_probability": 0.82,
  "confidence": 0.64,
  "top_features": [
    {
      "feature": "avg_rating",
      "importance": 0.30,
      "value": 4.5,
      "favorable": true,
      "contribution": 0.30
    },
    {
      "feature": "cancellation_rate",
      "importance": 0.25,
      "value": 0.08,
      "favorable": true,
      "contribution": 0.25
    },
    ...
  ],
  "prediction_source": "model",
  "model_version": "1.0.3",
  "latency_ms": 2.34
}
```

**Features:**

- Confidence score (0-1) based on prediction certainty
- Top contributing features with importance weights
- Favorable/unfavorable classification per feature
- Model version tracking for reproducibility

---

### 11.5 Soft Delete System

**File:** `routes/admin_routes.py`

**New Endpoints:**
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/admin/users/{id}/deactivate` | PATCH | Soft delete user |
| `/admin/users/{id}/reactivate` | PATCH | Reactivate user |
| `/admin/technicians/{id}/deactivate` | PATCH | Soft delete technician |
| `/admin/technicians/{id}/reactivate` | PATCH | Reactivate technician |
| `/admin/deactivated/users` | GET | List deactivated users |
| `/admin/deactivated/technicians` | GET | List deactivated technicians |

**Deactivation Fields:**

```javascript
{
  "is_active": false,
  "deactivated_at": DateTime,
  "deactivated_by": String
}
```

**Safeguards:**

- Warns if technician has active jobs
- Preserves all historical data
- Audit trail of who deactivated/reactivated

---

### 11.6 Performance Caching Layer

**File:** `utils/technician_selection.py`

**Cache Features:**

- LRU-based in-memory cache
- Configurable TTL (default: 5 minutes)
- Separate caches for distance and reliability predictions
- Hit rate monitoring

**Cached Operations:**
| Operation | TTL | Key Components |
|-----------|-----|----------------|
| Distance calculation | 5 min | lat1, lon1, lat2, lon2 |
| Reliability prediction | 5 min | technician_id, service_id |

**Management Endpoints:**
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/admin/cache/stats` | GET | Cache hit/miss statistics |
| `/admin/cache/clear` | POST | Clear all cached data |

**Statistics Response:**

```json
{
  "size": 150,
  "max_size": 1000,
  "ttl_seconds": 300,
  "hits": 2847,
  "misses": 423,
  "hit_rate": 0.871
}
```

**Production Note:** For distributed deployments, consider replacing with Redis for shared caching across instances.

---

## Summary

The RepairGo backend is a comprehensive home repair service platform with:

1. **User Management** - Registration, JWT auth, role-based access
2. **Technician Management** - Skills, location tracking, workload
3. **Service Management** - Full lifecycle from request to rating
4. **Smart Pricing** - ML-powered demand-based surge pricing
5. **Smart Assignment** - ML-powered technician scoring
6. **Fraud Detection** - ML anomaly detection with explainability
7. **Background Jobs** - Auto-reassignment with health monitoring
8. **Security** - Rate limiting, bcrypt, JWT, RBAC

### Production Enhancements (v2.0):

9. **Payment System** - Payment processing with refund support
10. **Real-Time Notifications** - WebSocket push notifications
11. **ML Model Registry** - Version tracking and metrics logging
12. **Model Explainability** - Feature contributions and confidence scores
13. **Soft Delete** - Safe deactivation with audit trail
14. **Performance Caching** - LRU cache for repeated computations

All ML features have fallback logic ensuring the system remains operational even without trained models.
