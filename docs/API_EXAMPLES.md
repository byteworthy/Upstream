# Upstream API Examples

Comprehensive curl examples for the Upstream Healthcare Platform API.

## Table of Contents

1. [Authentication](#1-authentication)
2. [Uploads](#2-uploads)
3. [Claims](#3-claims)
4. [Drift Events](#4-drift-events)
5. [Reports](#5-reports)
6. [Alerts](#6-alerts)
7. [Webhooks](#7-webhooks)

## Base URL

```
https://api.upstream.example.com
```

For local development:
```
http://localhost:8000
```

## 1. Authentication

All API endpoints (except `/health` and `/auth/*`) require JWT authentication. Include the access token in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

### 1.1 Login (Obtain JWT Token)

Request an access token and refresh token using your username and password.

**Endpoint:** `POST /api/v1/auth/token/`

**Request:**
```bash
curl -X POST https://api.upstream.example.com/api/v1/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "doctor@healthcorp.com",
    "password": "SecurePassword123!"
  }'
```

**Response (200 OK):**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoxLCJ1c2VybmFtZSI6ImRvY3RvckBoZWFsdGhjb3JwLmNvbSIsImV4cCI6MTcwNjI4NDgwMH0.abc123def456",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoxLCJ0eXBlIjoicmVmcmVzaCIsImV4cCI6MTcwNjM3MTIwMH0.ghi789jkl012"
}
```

**Token Expiration:**
- **Access Token**: 1 hour
- **Refresh Token**: 24 hours

**Error Response (401 Unauthorized):**
```json
{
  "detail": "No active account found with the given credentials"
}
```

### 1.2 Refresh Access Token

Obtain a new access token using your refresh token (without re-entering credentials).

**Endpoint:** `POST /api/v1/auth/token/refresh/`

**Request:**
```bash
curl -X POST https://api.upstream.example.com/api/v1/auth/token/refresh/ \
  -H "Content-Type: application/json" \
  -d '{
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoxLCJ0eXBlIjoicmVmcmVzaCIsImV4cCI6MTcwNjM3MTIwMH0.ghi789jkl012"
  }'
```

**Response (200 OK):**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoxLCJ1c2VybmFtZSI6ImRvY3RvckBoZWFsdGhjb3JwLmNvbSIsImV4cCI6MTcwNjI4ODQwMH0.xyz789abc012"
}
```

### 1.3 Verify Token

Check if a token is valid and not expired.

**Endpoint:** `POST /api/v1/auth/token/verify/`

**Request:**
```bash
curl -X POST https://api.upstream.example.com/api/v1/auth/token/verify/ \
  -H "Content-Type: application/json" \
  -d '{
    "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoxLCJ1c2VybmFtZSI6ImRvY3RvckBoZWFsdGhjb3JwLmNvbSIsImV4cCI6MTcwNjI4NDgwMH0.abc123def456"
  }'
```

**Response (200 OK):**
```json
{}
```

**Error Response (401 Unauthorized):**
```json
{
  "detail": "Token is invalid or expired",
  "code": "token_not_valid"
}
```

### 1.4 Using Authentication Tokens

For all subsequent API requests, include the access token in the Authorization header:

```bash
curl -X GET https://api.upstream.example.com/api/v1/uploads/ \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoxLCJ1c2VybmFtZSI6ImRvY3RvckBoZWFsdGhjb3JwLmNvbSIsImV4cCI6MTcwNjI4NDgwMH0.abc123def456"
```

## 2. Uploads

Manage file uploads for claims data ingestion.

### 2.1 List Uploads

Retrieve a paginated list of file uploads.

**Endpoint:** `GET /api/v1/uploads/`

**Request:**
```bash
curl -X GET "https://api.upstream.example.com/api/v1/uploads/?page=1&page_size=10" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response (200 OK):**
```json
{
  "count": 150,
  "next": "https://api.upstream.example.com/api/v1/uploads/?page=2&page_size=10",
  "previous": null,
  "results": [
    {
      "id": 42,
      "filename": "claims_2024_Q1.csv",
      "status": "success",
      "uploaded_at": "2024-01-15T10:30:00Z",
      "row_count": 5000
    },
    {
      "id": 41,
      "filename": "claims_2024_Q2.csv",
      "status": "processing",
      "uploaded_at": "2024-04-20T14:22:00Z",
      "row_count": 0
    },
    {
      "id": 40,
      "filename": "claims_2023_Q4.csv",
      "status": "failed",
      "uploaded_at": "2023-12-28T08:15:00Z",
      "row_count": 0,
      "error_message": "Invalid CSV format: missing required column 'payer'"
    }
  ]
}
```

### 2.2 Filter Uploads by Status

Filter uploads by status (success, failed, processing).

**Endpoint:** `GET /api/v1/uploads/?status=failed`

**Request:**
```bash
curl -X GET "https://api.upstream.example.com/api/v1/uploads/?status=failed" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response (200 OK):**
```json
{
  "count": 5,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 40,
      "filename": "claims_2023_Q4.csv",
      "status": "failed",
      "uploaded_at": "2023-12-28T08:15:00Z",
      "row_count": 0,
      "error_message": "Invalid CSV format: missing required column 'payer'"
    }
  ]
}
```

### 2.3 Get Upload Details

Retrieve detailed information for a specific upload.

**Endpoint:** `GET /api/v1/uploads/{id}/`

**Request:**
```bash
curl -X GET https://api.upstream.example.com/api/v1/uploads/42/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response (200 OK):**
```json
{
  "id": 42,
  "filename": "claims_2024_Q1.csv",
  "status": "success",
  "uploaded_at": "2024-01-15T10:30:00Z",
  "date_min": "2024-01-01",
  "date_max": "2024-03-31",
  "row_count": 5000,
  "customer": 1
}
```

### 2.4 Create Upload

Create a new file upload record.

**Endpoint:** `POST /api/v1/uploads/`

**Rate Limit:** 20 uploads/hour

**Permissions:** Requires `customer_admin` role

**Request:**
```bash
curl -X POST https://api.upstream.example.com/api/v1/uploads/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "claims_2024_Q3.csv",
    "date_min": "2024-07-01",
    "date_max": "2024-09-30"
  }'
```

**Response (201 Created):**
```json
{
  "id": 43,
  "filename": "claims_2024_Q3.csv",
  "status": "processing",
  "uploaded_at": "2024-07-15T10:30:00Z",
  "date_min": "2024-07-01",
  "date_max": "2024-09-30",
  "row_count": 0
}
```

**Error Response (403 Forbidden):**
```json
{
  "detail": "You do not have permission to perform this action. Requires customer_admin role."
}
```

### 2.5 Get Upload Statistics

Retrieve aggregated upload statistics for your customer.

**Endpoint:** `GET /api/v1/uploads/stats/`

**Request:**
```bash
curl -X GET https://api.upstream.example.com/api/v1/uploads/stats/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response (200 OK):**
```json
{
  "total": 150,
  "success": 140,
  "failed": 5,
  "processing": 5,
  "total_rows": 125000
}
```

## 3. Claims

Query and analyze claim records.

### 3.1 List Claims (Paginated)

Retrieve a paginated list of claim records.

**Endpoint:** `GET /api/v1/claims/`

**Rate Limit:** 2000 requests/hour

**Request:**
```bash
curl -X GET "https://api.upstream.example.com/api/v1/claims/?page=1&page_size=10" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response (200 OK):**
```json
{
  "count": 125000,
  "next": "https://api.upstream.example.com/api/v1/claims/?page=2&page_size=10",
  "previous": null,
  "results": [
    {
      "id": 1001,
      "payer": "Blue Cross Blue Shield",
      "cpt": "99213",
      "outcome": "PAID",
      "submitted_date": "2024-01-10",
      "decided_date": "2024-01-25",
      "allowed_amount": "150.00"
    },
    {
      "id": 1002,
      "payer": "Aetna",
      "cpt": "99214",
      "outcome": "DENIED",
      "submitted_date": "2024-01-12",
      "decided_date": "2024-01-28",
      "allowed_amount": "0.00",
      "denial_reason_code": "CO-97"
    }
  ]
}
```

### 3.2 Filter Claims by Payer

Filter claims by a specific payer.

**Endpoint:** `GET /api/v1/claims/?payer=Aetna`

**Request:**
```bash
curl -X GET "https://api.upstream.example.com/api/v1/claims/?payer=Aetna&page=1&page_size=10" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response (200 OK):**
```json
{
  "count": 3156,
  "next": "https://api.upstream.example.com/api/v1/claims/?payer=Aetna&page=2&page_size=10",
  "previous": null,
  "results": [
    {
      "id": 1002,
      "payer": "Aetna",
      "cpt": "99214",
      "outcome": "DENIED",
      "submitted_date": "2024-01-12",
      "decided_date": "2024-01-28",
      "allowed_amount": "0.00",
      "denial_reason_code": "CO-97"
    }
  ]
}
```

### 3.3 Filter Claims by Outcome

Filter claims by outcome (PAID, DENIED, OTHER).

**Endpoint:** `GET /api/v1/claims/?outcome=DENIED`

**Request:**
```bash
curl -X GET "https://api.upstream.example.com/api/v1/claims/?outcome=DENIED&page=1&page_size=10" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response (200 OK):**
```json
{
  "count": 12500,
  "next": "https://api.upstream.example.com/api/v1/claims/?outcome=DENIED&page=2&page_size=10",
  "previous": null,
  "results": [
    {
      "id": 1002,
      "payer": "Aetna",
      "cpt": "99214",
      "outcome": "DENIED",
      "submitted_date": "2024-01-12",
      "decided_date": "2024-01-28",
      "allowed_amount": "0.00",
      "denial_reason_code": "CO-97"
    }
  ]
}
```

### 3.4 Filter Claims by Date Range

Filter claims submitted within a specific date range.

**Endpoint:** `GET /api/v1/claims/?submitted_date_after=2024-01-01&submitted_date_before=2024-01-31`

**Request:**
```bash
curl -X GET "https://api.upstream.example.com/api/v1/claims/?submitted_date_after=2024-01-01&submitted_date_before=2024-01-31&page=1&page_size=10" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response (200 OK):**
```json
{
  "count": 8500,
  "next": "https://api.upstream.example.com/api/v1/claims/?submitted_date_after=2024-01-01&submitted_date_before=2024-01-31&page=2&page_size=10",
  "previous": null,
  "results": [
    {
      "id": 1001,
      "payer": "Blue Cross Blue Shield",
      "cpt": "99213",
      "outcome": "PAID",
      "submitted_date": "2024-01-10",
      "decided_date": "2024-01-25",
      "allowed_amount": "150.00"
    }
  ]
}
```

### 3.5 Get Payer Summary Statistics

Retrieve aggregated statistics by payer for a date range.

**Endpoint:** `GET /api/v1/claims/payer_summary/`

**Request:**
```bash
curl -X GET "https://api.upstream.example.com/api/v1/claims/payer_summary/?start_date=2024-01-01&end_date=2024-03-31" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response (200 OK):**
```json
{
  "count": 15,
  "next": "https://api.upstream.example.com/api/v1/claims/payer_summary/?start_date=2024-01-01&end_date=2024-03-31&page=2",
  "previous": null,
  "results": [
    {
      "payer": "Blue Cross Blue Shield",
      "total_claims": 5234,
      "paid_count": 4812,
      "denied_count": 398,
      "other_count": 24,
      "denial_rate": 7.61,
      "avg_allowed_amount": "187.50"
    },
    {
      "payer": "Aetna",
      "total_claims": 3156,
      "paid_count": 2789,
      "denied_count": 345,
      "other_count": 22,
      "denial_rate": 10.93,
      "avg_allowed_amount": "165.23"
    },
    {
      "payer": "UnitedHealthcare",
      "total_claims": 2890,
      "paid_count": 2601,
      "denied_count": 276,
      "other_count": 13,
      "denial_rate": 9.55,
      "avg_allowed_amount": "192.45"
    }
  ]
}
```

## 4. Drift Events

Monitor payer behavior drift and anomalies.

### 4.1 List Drift Events

Retrieve a paginated list of drift events.

**Endpoint:** `GET /api/v1/drift-events/`

**Rate Limit:** 2000 requests/hour

**Request:**
```bash
curl -X GET "https://api.upstream.example.com/api/v1/drift-events/?page=1&page_size=10" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response (200 OK):**
```json
{
  "count": 42,
  "next": "https://api.upstream.example.com/api/v1/drift-events/?page=2&page_size=10",
  "previous": null,
  "results": [
    {
      "id": 1,
      "payer": "Blue Cross Blue Shield",
      "cpt_group": "Office Visits",
      "drift_type": "denial_rate",
      "severity": 0.85,
      "baseline_value": "5.2",
      "current_value": "18.7",
      "delta_value": "13.5",
      "created_at": "2024-01-15T10:30:00Z"
    },
    {
      "id": 2,
      "payer": "Aetna",
      "cpt_group": "Imaging",
      "drift_type": "decision_time",
      "severity": 0.72,
      "baseline_value": "12.3",
      "current_value": "28.9",
      "delta_value": "16.6",
      "created_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

### 4.2 Filter Drift Events by Severity

Filter drift events by minimum severity threshold.

**Endpoint:** `GET /api/v1/drift-events/?severity_min=0.8`

**Request:**
```bash
curl -X GET "https://api.upstream.example.com/api/v1/drift-events/?severity_min=0.8" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response (200 OK):**
```json
{
  "count": 8,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "payer": "Blue Cross Blue Shield",
      "cpt_group": "Office Visits",
      "drift_type": "denial_rate",
      "severity": 0.85,
      "baseline_value": "5.2",
      "current_value": "18.7",
      "delta_value": "13.5",
      "created_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

### 4.3 Filter Drift Events by Payer and Drift Type

Combine multiple filters to narrow results.

**Endpoint:** `GET /api/v1/drift-events/?payer=Aetna&drift_type=denial_rate`

**Request:**
```bash
curl -X GET "https://api.upstream.example.com/api/v1/drift-events/?payer=Aetna&drift_type=denial_rate" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response (200 OK):**
```json
{
  "count": 3,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 5,
      "payer": "Aetna",
      "cpt_group": "Office Visits",
      "drift_type": "denial_rate",
      "severity": 0.68,
      "baseline_value": "8.1",
      "current_value": "15.3",
      "delta_value": "7.2",
      "created_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

### 4.4 Get Active Drift Events

Retrieve drift events from the most recent successful report run.

**Endpoint:** `GET /api/v1/drift-events/active/`

**Request:**
```bash
curl -X GET "https://api.upstream.example.com/api/v1/drift-events/active/?page=1&page_size=10" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response (200 OK):**
```json
{
  "count": 15,
  "next": "https://api.upstream.example.com/api/v1/drift-events/active/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "payer": "Blue Cross Blue Shield",
      "cpt_group": "Office Visits",
      "drift_type": "denial_rate",
      "severity": 0.92,
      "baseline_value": "5.2",
      "current_value": "18.7",
      "delta_value": "13.5",
      "created_at": "2024-01-20T10:30:00Z",
      "report_run": 42
    }
  ]
}
```

### 4.5 Get Drift Event Details

Retrieve detailed information for a specific drift event.

**Endpoint:** `GET /api/v1/drift-events/{id}/`

**Request:**
```bash
curl -X GET https://api.upstream.example.com/api/v1/drift-events/1/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response (200 OK):**
```json
{
  "id": 1,
  "payer": "Blue Cross Blue Shield",
  "cpt_group": "Office Visits",
  "drift_type": "denial_rate",
  "severity": 0.85,
  "baseline_value": "5.2",
  "current_value": "18.7",
  "delta_value": "13.5",
  "created_at": "2024-01-15T10:30:00Z",
  "report_run": 42,
  "customer": 1
}
```

## 5. Reports

Generate and manage payer drift reports.

### 5.1 List Report Runs

Retrieve a paginated list of report runs.

**Endpoint:** `GET /api/v1/reports/`

**Request:**
```bash
curl -X GET "https://api.upstream.example.com/api/v1/reports/?page=1&page_size=10" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response (200 OK):**
```json
{
  "count": 50,
  "next": "https://api.upstream.example.com/api/v1/reports/?page=2&page_size=10",
  "previous": null,
  "results": [
    {
      "id": 42,
      "run_type": "weekly",
      "status": "success",
      "started_at": "2024-01-20T10:30:00Z",
      "finished_at": "2024-01-20T10:35:22Z",
      "drift_event_count": 15
    },
    {
      "id": 41,
      "run_type": "weekly",
      "status": "success",
      "started_at": "2024-01-13T10:30:00Z",
      "finished_at": "2024-01-13T10:34:18Z",
      "drift_event_count": 12
    }
  ]
}
```

### 5.2 Get Report Run Details

Retrieve detailed information for a specific report run.

**Endpoint:** `GET /api/v1/reports/{id}/`

**Request:**
```bash
curl -X GET https://api.upstream.example.com/api/v1/reports/42/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response (200 OK):**
```json
{
  "id": 42,
  "run_type": "weekly",
  "status": "success",
  "started_at": "2024-01-20T10:30:00Z",
  "finished_at": "2024-01-20T10:35:22Z",
  "drift_events": [
    {
      "id": 1,
      "payer": "Blue Cross Blue Shield",
      "cpt_group": "Office Visits",
      "drift_type": "denial_rate",
      "severity": 0.92
    }
  ],
  "drift_event_count": 15
}
```

### 5.3 Trigger New Report Run

Create and queue a new payer drift report run.

**Endpoint:** `POST /api/v1/reports/trigger/`

**Rate Limit:** 10 requests/hour

**Permissions:** Requires `customer_admin` role

**Request:**
```bash
curl -X POST https://api.upstream.example.com/api/v1/reports/trigger/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response (202 Accepted):**
```json
{
  "id": 43,
  "run_type": "weekly",
  "status": "running",
  "started_at": "2024-01-25T10:30:00Z",
  "finished_at": null,
  "drift_event_count": 0
}
```

**Note:** The report runs asynchronously. Poll the report endpoint to check status.

### 5.4 Poll Report Status

Check if a report run has completed.

**Endpoint:** `GET /api/v1/reports/{id}/`

**Request:**
```bash
curl -X GET https://api.upstream.example.com/api/v1/reports/43/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response (200 OK) - Running:**
```json
{
  "id": 43,
  "run_type": "weekly",
  "status": "running",
  "started_at": "2024-01-25T10:30:00Z",
  "finished_at": null,
  "drift_event_count": 0
}
```

**Response (200 OK) - Completed:**
```json
{
  "id": 43,
  "run_type": "weekly",
  "status": "success",
  "started_at": "2024-01-25T10:30:00Z",
  "finished_at": "2024-01-25T10:35:45Z",
  "drift_event_count": 18
}
```

### 5.5 Get Dashboard Overview

Retrieve dashboard overview data including denial trends and top drift payers.

**Endpoint:** `GET /api/v1/dashboard/`

**Request:**
```bash
curl -X GET https://api.upstream.example.com/api/v1/dashboard/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response (200 OK):**
```json
{
  "total_claims": 125000,
  "total_uploads": 42,
  "active_drift_events": 15,
  "last_report_date": "2024-01-20T10:30:00Z",
  "denial_rate_trend": [
    {
      "month": "2023-08",
      "denial_rate": 8.5,
      "total_claims": 18500,
      "denied_claims": 1573
    },
    {
      "month": "2023-09",
      "denial_rate": 9.2,
      "total_claims": 19200,
      "denied_claims": 1766
    },
    {
      "month": "2023-10",
      "denial_rate": 10.1,
      "total_claims": 20100,
      "denied_claims": 2030
    }
  ],
  "top_drift_payers": [
    {
      "payer": "Blue Cross Blue Shield",
      "severity": 0.92,
      "delta_value": "15.3"
    },
    {
      "payer": "Aetna",
      "severity": 0.87,
      "delta_value": "12.8"
    }
  ]
}
```

## 6. Alerts

Manage alert events and submit operator feedback.

### 6.1 List Alert Events

Retrieve a paginated list of alert events.

**Endpoint:** `GET /api/v1/alerts/`

**Request:**
```bash
curl -X GET "https://api.upstream.example.com/api/v1/alerts/?page=1&page_size=10" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response (200 OK):**
```json
{
  "count": 25,
  "next": "https://api.upstream.example.com/api/v1/alerts/?page=2&page_size=10",
  "previous": null,
  "results": [
    {
      "id": 101,
      "status": "pending",
      "triggered_at": "2024-01-20T10:35:00Z",
      "alert_rule": {
        "id": 5,
        "name": "High Denial Rate Alert",
        "severity": "critical"
      },
      "drift_event": {
        "id": 1,
        "payer": "Blue Cross Blue Shield",
        "severity": 0.92
      },
      "operator_judgments": []
    }
  ]
}
```

### 6.2 Get Alert Event Details

Retrieve detailed information for a specific alert event.

**Endpoint:** `GET /api/v1/alerts/{id}/`

**Request:**
```bash
curl -X GET https://api.upstream.example.com/api/v1/alerts/101/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response (200 OK):**
```json
{
  "id": 101,
  "status": "pending",
  "triggered_at": "2024-01-20T10:35:00Z",
  "alert_rule": {
    "id": 5,
    "name": "High Denial Rate Alert",
    "severity": "critical",
    "threshold": 0.8
  },
  "drift_event": {
    "id": 1,
    "payer": "Blue Cross Blue Shield",
    "cpt_group": "Office Visits",
    "drift_type": "denial_rate",
    "severity": 0.92,
    "delta_value": "15.3"
  },
  "operator_judgments": []
}
```

### 6.3 Submit Operator Feedback (Real Alert)

Submit feedback indicating an alert is a real issue with actionable outcomes.

**Endpoint:** `POST /api/v1/alerts/{id}/feedback/`

**Permissions:** Requires `customer_admin` role

**Request:**
```bash
curl -X POST https://api.upstream.example.com/api/v1/alerts/101/feedback/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "verdict": "real",
    "reason_codes": ["payer_policy_change"],
    "recovered_amount": "5000.00",
    "recovered_date": "2024-03-15",
    "notes": "Contacted payer and confirmed policy change effective Feb 1. Successfully appealed 50 claims."
  }'
```

**Response (201 Created):**
```json
{
  "id": 42,
  "verdict": "real",
  "reason_codes": ["payer_policy_change"],
  "recovered_amount": "5000.00",
  "recovered_date": "2024-03-15",
  "notes": "Contacted payer and confirmed policy change effective Feb 1. Successfully appealed 50 claims.",
  "created_at": "2024-01-21T14:30:00Z",
  "operator": {
    "id": 10,
    "username": "doctor@healthcorp.com"
  }
}
```

### 6.4 Submit Operator Feedback (Noise)

Submit feedback indicating an alert is a false positive.

**Endpoint:** `POST /api/v1/alerts/{id}/feedback/`

**Request:**
```bash
curl -X POST https://api.upstream.example.com/api/v1/alerts/102/feedback/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "verdict": "noise",
    "reason_codes": ["data_quality_issue"],
    "notes": "False positive due to incomplete data upload. Re-uploaded corrected file."
  }'
```

**Response (201 Created):**
```json
{
  "id": 43,
  "verdict": "noise",
  "reason_codes": ["data_quality_issue"],
  "recovered_amount": null,
  "recovered_date": null,
  "notes": "False positive due to incomplete data upload. Re-uploaded corrected file.",
  "created_at": "2024-01-21T15:00:00Z",
  "operator": {
    "id": 10,
    "username": "doctor@healthcorp.com"
  }
}
```

### 6.5 Filter Alerts by Status

Filter alert events by status (pending, acknowledged, resolved).

**Endpoint:** `GET /api/v1/alerts/?status=pending`

**Request:**
```bash
curl -X GET "https://api.upstream.example.com/api/v1/alerts/?status=pending" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response (200 OK):**
```json
{
  "count": 8,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 101,
      "status": "pending",
      "triggered_at": "2024-01-20T10:35:00Z",
      "alert_rule": {
        "id": 5,
        "name": "High Denial Rate Alert"
      }
    }
  ]
}
```

## 7. Webhooks

Ingest data via webhook endpoints.

### 7.1 Webhook Ingestion

Send claims data via webhook with token authentication.

**Endpoint:** `POST /api/v1/ingest/webhook/`

**Authentication:** Bearer token (Ingestion Token, not JWT)

**Request:**
```bash
curl -X POST https://api.upstream.example.com/api/v1/ingest/webhook/ \
  -H "Authorization: Bearer INGESTION_TOKEN_12345" \
  -H "Content-Type: application/json" \
  -H "X-Idempotency-Key: unique-request-id-001" \
  -d '{
    "claims": [
      {
        "payer": "Blue Cross Blue Shield",
        "cpt": "99213",
        "submitted_date": "2024-01-15",
        "decided_date": "2024-02-01",
        "outcome": "PAID",
        "allowed_amount": "150.00"
      },
      {
        "payer": "Aetna",
        "cpt": "99214",
        "submitted_date": "2024-01-16",
        "decided_date": "2024-02-02",
        "outcome": "DENIED",
        "allowed_amount": "0.00",
        "denial_reason_code": "CO-97"
      }
    ]
  }'
```

**Response (202 Accepted):**
```json
{
  "status": "accepted",
  "ingestion_id": 123,
  "message": "Payload received and queued for processing"
}
```

**Note:** Processing is asynchronous. Check ingestion status via ingestion_id.

### 7.2 Webhook Authentication Error

Missing or invalid ingestion token.

**Request:**
```bash
curl -X POST https://api.upstream.example.com/api/v1/ingest/webhook/ \
  -H "Content-Type: application/json" \
  -d '{
    "claims": [{"payer": "BCBS", "cpt": "99213"}]
  }'
```

**Response (401 Unauthorized):**
```json
{
  "error": "Missing or invalid authorization header"
}
```

### 7.3 Idempotent Webhook Requests

Use idempotency keys to prevent duplicate processing.

**Request:**
```bash
curl -X POST https://api.upstream.example.com/api/v1/ingest/webhook/ \
  -H "Authorization: Bearer INGESTION_TOKEN_12345" \
  -H "Content-Type: application/json" \
  -H "X-Idempotency-Key: unique-request-id-002" \
  -d '{
    "claims": [
      {
        "payer": "UnitedHealthcare",
        "cpt": "99215",
        "submitted_date": "2024-01-17",
        "decided_date": "2024-02-03",
        "outcome": "PAID",
        "allowed_amount": "200.00"
      }
    ]
  }'
```

**Response (202 Accepted):**
```json
{
  "status": "accepted",
  "ingestion_id": 124,
  "message": "Payload received and queued for processing"
}
```

**Duplicate Request (same idempotency key):**
```json
{
  "status": "duplicate",
  "ingestion_id": 124,
  "message": "Request already processed"
}
```

### 7.4 Empty Payload Error

Webhook payload must not be empty.

**Request:**
```bash
curl -X POST https://api.upstream.example.com/api/v1/ingest/webhook/ \
  -H "Authorization: Bearer INGESTION_TOKEN_12345" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Response (400 Bad Request):**
```json
{
  "error": "Empty payload"
}
```

### 7.5 Check API Health

Verify API is running and accessible (no authentication required).

**Endpoint:** `GET /api/v1/health/`

**Request:**
```bash
curl -X GET https://api.upstream.example.com/api/v1/health/
```

**Response (200 OK):**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2024-01-26T10:30:00Z"
}
```

---

## Common Error Responses

### 401 Unauthorized

Missing or invalid authentication token.

```json
{
  "detail": "Authentication credentials were not provided."
}
```

Or:

```json
{
  "detail": "Given token not valid for any token type",
  "code": "token_not_valid"
}
```

### 403 Forbidden

Insufficient permissions to perform action.

```json
{
  "detail": "You do not have permission to perform this action."
}
```

### 404 Not Found

Resource does not exist or is not accessible to your customer.

```json
{
  "detail": "Not found."
}
```

### 429 Too Many Requests

Rate limit exceeded.

```json
{
  "detail": "Request was throttled. Expected available in 600 seconds."
}
```

---

## Rate Limits

| Endpoint | Rate Limit |
|----------|-----------|
| `/auth/token/` (login) | 5 requests / 15 minutes |
| `/uploads/` (create) | 20 requests / hour |
| `/reports/trigger/` | 10 requests / hour |
| `/claims/` (list) | 2000 requests / hour |
| `/drift-events/` (list) | 2000 requests / hour |
| Other read endpoints | Liberal limits (2000+ requests/hour) |

---

## RBAC Roles

| Role | Permissions |
|------|------------|
| **Superuser** | Full access to all resources across all customers |
| **Customer Admin** | Full CRUD access to customer's data (uploads, reports, alerts) |
| **Customer Viewer** | Read-only access to customer's data |

---

## Support

For API support or questions, contact: support@upstream.example.com

For API status and updates: https://status.upstream.example.com
