# Specialty Module System

## Overview

Upstream uses a "Smart Defaults with Optional Expansion" architecture for specialty modules. This system allows customers to:

1. Select a **primary specialty** during onboarding (Dialysis, ABA, Imaging, Home Health, PT/OT)
2. UI shows only features relevant to enabled specialties
3. Settings allows enabling additional specialty modules (+$99/mo each)
4. Alerts are filtered to show only alerts for enabled specialties
5. Dashboard widgets appear conditionally based on enabled specialties
6. Backend allows full access - this is purely a UI preference system

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Customer Model                           │
│  specialty_type (primary)  │  specialty_modules (add-ons)   │
└─────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              enabled_specialties property                   │
│  Returns: [primary] + [enabled modules]                     │
└─────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              has_specialty(code) method                     │
│  1. Check if code == primary (case-insensitive)            │
│  2. Check if code in enabled_specialties                   │
└─────────────────────────────────────────────────────────────┘
```

## Specialty Types

| Code | Display Name | Description |
|------|--------------|-------------|
| DIALYSIS | Dialysis | MA payment variance detection |
| ABA | ABA Therapy | Authorization tracking & unit monitoring |
| PTOT | PT/OT | 8-minute rule & G-code validation |
| IMAGING | Imaging | Prior auth requirements & RBM tracking |
| HOME_HEALTH | Home Health | PDGM validation & F2F tracking |

## Backend API

### Customer Endpoints

#### GET /api/v1/customers/me/
Returns current customer with specialty information.

**Response:**
```json
{
  "id": 1,
  "name": "Test Dialysis Center",
  "specialty_type": "DIALYSIS",
  "specialty_modules": [
    {
      "id": 1,
      "specialty": "DIALYSIS",
      "enabled": true,
      "enabled_at": "2024-01-01T00:00:00Z",
      "is_primary": true
    }
  ],
  "enabled_specialties": ["DIALYSIS"]
}
```

#### POST /api/v1/customers/set_primary_specialty/
Set primary specialty during onboarding.

**Request:**
```json
{
  "specialty_type": "DIALYSIS"
}
```

#### POST /api/v1/customers/enable_specialty/
Enable an additional specialty module.

**Request:**
```json
{
  "specialty": "ABA"
}
```

#### POST /api/v1/customers/disable_specialty/
Disable a specialty module (cannot disable primary).

**Request:**
```json
{
  "specialty": "ABA"
}
```

## Backend Usage

### Check if customer has specialty enabled

```python
from upstream.models import Customer

customer = Customer.objects.get(id=1)

# Check if specialty is enabled (includes primary)
if customer.has_specialty("DIALYSIS"):
    # Show dialysis-specific features
    pass

# Get all enabled specialties
enabled = customer.enabled_specialties  # ['DIALYSIS', 'ABA']
```

### Filter alerts by enabled specialties

```python
from upstream.alerts.models import AlertEvent

# Get alerts for customer's enabled specialties
alerts = AlertEvent.objects.filter(
    customer=customer,
    specialty__in=customer.enabled_specialties + ['CORE']
)
```

## Frontend Usage

### CustomerContext

The `CustomerContext` provides customer profile and specialty methods.

```typescript
import { useCustomer } from '@/contexts/CustomerContext';

function MyComponent() {
  const { customer, loading, hasSpecialty, enableSpecialty, disableSpecialty } = useCustomer();

  // Check if specialty is enabled
  if (hasSpecialty('DIALYSIS')) {
    // Render dialysis-specific UI
  }

  // Enable a new specialty (with optimistic update)
  const handleEnable = async () => {
    try {
      await enableSpecialty('ABA');
    } catch (error) {
      // Handles rollback automatically
    }
  };
}
```

### Route Guards

Use `SpecialtyRoute` to protect routes by specialty.

```typescript
import { SpecialtyRoute } from '@/components/guards';

// In router
<Route
  path="/specialty/dialysis"
  element={
    <SpecialtyRoute specialty="DIALYSIS">
      <DialysisPage />
    </SpecialtyRoute>
  }
/>
```

### Conditional Rendering

```typescript
import { useCustomer, SPECIALTY_LABELS } from '@/contexts/CustomerContext';

function Dashboard() {
  const { hasSpecialty } = useCustomer();

  return (
    <div>
      {hasSpecialty('DIALYSIS') && <DialysisWidget />}
      {hasSpecialty('ABA') && <ABAWidget />}
    </div>
  );
}
```

### Specialty Labels

```typescript
import { SPECIALTY_LABELS, SPECIALTY_DESCRIPTIONS } from '@/contexts/CustomerContext';

// SPECIALTY_LABELS = {
//   DIALYSIS: 'Dialysis',
//   ABA: 'ABA Therapy',
//   PTOT: 'PT/OT',
//   IMAGING: 'Imaging',
//   HOME_HEALTH: 'Home Health',
// }
```

## Adding a New Specialty

### 1. Update Backend Models

Add to `SPECIALTY_CHOICES` in `upstream/models.py`:

```python
class Customer(models.Model):
    SPECIALTY_CHOICES = [
        ("DIALYSIS", "Dialysis"),
        ("ABA", "ABA Therapy"),
        ("PTOT", "PT/OT"),
        ("IMAGING", "Imaging"),
        ("HOME_HEALTH", "Home Health"),
        ("NEW_SPECIALTY", "New Specialty"),  # Add here
    ]
```

### 2. Update Alert Mapping

Add to `ALERT_TYPE_TO_SPECIALTY` in `upstream/services/specialty_utils.py`:

```python
ALERT_TYPE_TO_SPECIALTY = {
    # ... existing mappings
    'new_specialty_alert': 'NEW_SPECIALTY',
}
```

### 3. Update Frontend Types

Add to `SpecialtyType` in `frontend/src/types/api.d.ts`:

```typescript
export type SpecialtyType = 'DIALYSIS' | 'ABA' | 'PTOT' | 'IMAGING' | 'HOME_HEALTH' | 'NEW_SPECIALTY';
```

### 4. Update Frontend Labels

Add to `SPECIALTY_LABELS` and `SPECIALTY_DESCRIPTIONS` in `frontend/src/contexts/CustomerContext.tsx`:

```typescript
export const SPECIALTY_LABELS: Record<SpecialtyType, string> = {
  // ... existing
  NEW_SPECIALTY: 'New Specialty',
};

export const SPECIALTY_DESCRIPTIONS: Record<SpecialtyType, string> = {
  // ... existing
  NEW_SPECIALTY: 'Description of new specialty features',
};
```

### 5. Create Specialty Page

Create `frontend/src/pages/specialty/NewSpecialtyPage.tsx` and add route in `App.tsx`.

### 6. Update Sidebar Navigation

Add to `SPECIALTY_NAV_CONFIG` in `frontend/src/components/layout/Sidebar.tsx`.

## Database Schema

### CustomerSpecialtyModule Table

```sql
CREATE TABLE customer_specialty_module (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customer(id),
    specialty VARCHAR(20) NOT NULL,
    enabled BOOLEAN DEFAULT true,
    enabled_at TIMESTAMP,
    is_primary BOOLEAN DEFAULT false,
    stripe_subscription_item_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(customer_id, specialty)
);

CREATE INDEX idx_customer_specialty ON customer_specialty_module(customer_id, specialty);
CREATE INDEX idx_enabled_specialty ON customer_specialty_module(customer_id, enabled);
```

## Billing Integration

Specialty modules integrate with Stripe for billing:

1. When `enableSpecialty` is called, a Stripe subscription item is created
2. The `stripe_subscription_item_id` is stored in `CustomerSpecialtyModule`
3. When `disableSpecialty` is called, the subscription item is cancelled
4. Primary specialty is included in base subscription

## Testing

### Backend Tests

```bash
python manage.py test upstream.tests.test_specialty_modules -v 2
```

### Frontend Tests

```bash
cd frontend && npm run test -- --run src/contexts/__tests__/CustomerContext.test.tsx
```

## Migration Notes

- Migration `0036_customer_specialty_modules.py` creates the schema
- Backfill function creates primary module for existing customers
- No data loss - existing customers retain their specialty_type
