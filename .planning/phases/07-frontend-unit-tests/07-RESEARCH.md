# Phase 7: Frontend Unit Tests for Critical Components - Research

**Researched:** 2026-02-02
**Domain:** React Testing (Vitest + React Testing Library)
**Confidence:** HIGH

## Summary

This phase focuses on achieving 80%+ test coverage for the specialty module system in the Upstream frontend. The codebase already has a well-configured Vitest + React Testing Library setup with existing tests for CustomerContext that can serve as patterns for additional tests.

Key components requiring tests:
1. **CustomerContext** - Already has comprehensive tests (14 passing tests) covering `enableSpecialty`, `disableSpecialty`, `hasSpecialty`, and error handling
2. **SpecialtyRoute** - Route guard component that needs tests for redirect behavior based on specialty access
3. **Settings/SpecialtyModulesCard** - Toggle functionality for enabling/disabling specialty modules
4. **Dashboard/SpecialtyWidgets** - Conditional rendering based on enabled specialties
5. **Sidebar** - Dynamic navigation that updates based on specialty configuration

**Primary recommendation:** Extend the existing test patterns from CustomerContext.test.tsx, using custom wrapper functions for testing components that consume CustomerContext and MemoryRouter for testing routing behavior.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Vitest | ^4.0.18 | Test runner | Fast, native ESM, Jest-compatible API, already configured |
| @testing-library/react | ^16.3.2 | React component testing | Tests user behavior, not implementation |
| @testing-library/jest-dom | ^6.9.1 | DOM matchers | Extended assertions for DOM state |
| @vitest/coverage-v8 | ^4.0.17 | Coverage provider | Native V8 coverage, fast and accurate |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| @testing-library/user-event | ^14.6.1 | User interaction simulation | Testing clicks, typing, form interactions |
| jsdom | ^27.4.0 | DOM environment | Required for component rendering in tests |

### Already Configured
The project has a complete test setup:
- `vitest.config.ts` - Configured with jsdom, globals, path aliases
- `src/test/setup.ts` - Cleanup, matchMedia mock, ResizeObserver mock
- Path alias `@/` resolved for imports

**No additional installation required** - all dependencies are present.

## Architecture Patterns

### Recommended Test File Structure
```
frontend/src/
├── contexts/
│   └── __tests__/
│       └── CustomerContext.test.tsx  # EXISTS - 14 tests passing
├── components/
│   └── guards/
│       └── __tests__/
│           └── SpecialtyRoute.test.tsx  # TO CREATE
├── pages/
│   └── __tests__/
│       └── Settings.test.tsx  # TO CREATE (for SpecialtyModulesCard)
│       └── Dashboard.test.tsx  # TO CREATE (for SpecialtyWidgets)
└── components/
    └── layout/
        └── __tests__/
            └── Sidebar.test.tsx  # TO CREATE
```

### Pattern 1: Context Provider Wrapper
**What:** Wrap components that consume CustomerContext with a provider for testing
**When to use:** Testing any component that calls `useCustomer()`
**Example:**
```typescript
// Source: Existing pattern from CustomerContext.test.tsx
const mockCustomer: CustomerProfile = {
  id: 1,
  name: 'Test Customer',
  specialty_type: 'DIALYSIS',
  specialty_modules: [
    {
      id: 1,
      specialty: 'DIALYSIS',
      enabled: true,
      enabled_at: '2024-01-01T00:00:00Z',
      is_primary: true,
    },
  ],
  enabled_specialties: ['DIALYSIS'],
};

// Setup fetch mock before render
(globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
  ok: true,
  json: () => Promise.resolve(mockCustomer),
});

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <CustomerProvider>{children}</CustomerProvider>
);

// Use in renderHook or render
render(<ComponentUnderTest />, { wrapper });
```

### Pattern 2: MemoryRouter for Route Testing
**What:** Use MemoryRouter to test components that use react-router-dom
**When to use:** Testing SpecialtyRoute, Sidebar, any navigation-dependent component
**Example:**
```typescript
// Source: Testing Library docs - https://testing-library.com/docs/example-react-router/
import { MemoryRouter } from 'react-router-dom';

const renderWithRouter = (
  ui: React.ReactElement,
  { route = '/', ...renderOptions } = {}
) => {
  return render(
    <MemoryRouter initialEntries={[route]}>
      {ui}
    </MemoryRouter>,
    renderOptions
  );
};

// Test redirect behavior
test('redirects when specialty not enabled', async () => {
  (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
    ok: true,
    json: () => Promise.resolve(mockCustomerWithoutABA),
  });

  render(
    <MemoryRouter initialEntries={['/specialty/aba']}>
      <CustomerProvider>
        <Routes>
          <Route path="/dashboard" element={<div>Dashboard</div>} />
          <Route
            path="/specialty/aba"
            element={
              <SpecialtyRoute specialty="ABA">
                <div>ABA Page</div>
              </SpecialtyRoute>
            }
          />
        </Routes>
      </CustomerProvider>
    </MemoryRouter>
  );

  await waitFor(() => {
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
  });
});
```

### Pattern 3: Mocking External Dependencies
**What:** Mock sonner toast and other external libraries
**When to use:** Testing components that show toasts or call external services
**Example:**
```typescript
// Source: Existing pattern from CustomerContext.test.tsx
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}));
```

### Anti-Patterns to Avoid
- **Testing implementation details:** Don't test internal state, test what users see
- **Mocking too much:** Use real providers when possible, mock only external services (fetch, toast)
- **Not waiting for async updates:** Always use `waitFor` or `findBy*` queries for async operations
- **Testing with real API calls:** Always mock fetch for predictable tests

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| DOM assertions | Custom matchers | @testing-library/jest-dom | `.toBeInTheDocument()`, `.toHaveTextContent()` etc. |
| User interactions | Manual events | @testing-library/user-event | Handles focus, selection, event ordering correctly |
| Async waiting | setTimeout/manual polling | `waitFor`, `findBy*` queries | Built-in retry and timeout handling |
| Router testing | Mocking navigate functions | MemoryRouter | Full routing behavior without complex mocks |
| Coverage reporting | Custom tracking | @vitest/coverage-v8 | AST-based, accurate, fast |

**Key insight:** React Testing Library encourages testing from the user's perspective. If you're reaching into component internals, you're likely testing implementation, not behavior.

## Common Pitfalls

### Pitfall 1: Not Waiting for Provider Data
**What goes wrong:** Tests fail because CustomerContext hasn't loaded yet
**Why it happens:** CustomerContext fetches data on mount asynchronously
**How to avoid:** Always `await waitFor(() => { expect(result.current.loading).toBe(false); })` before assertions
**Warning signs:** Intermittent test failures, assertions on `null` values

### Pitfall 2: Missing Router Context
**What goes wrong:** "useLocation/useNavigate must be used within a Router" errors
**Why it happens:** Components using react-router hooks rendered without MemoryRouter
**How to avoid:** Wrap with MemoryRouter in test wrapper
**Warning signs:** Error messages mentioning Router context

### Pitfall 3: Not Cleaning Up Mocks
**What goes wrong:** Test pollution, inconsistent results between runs
**Why it happens:** Mock state persists across tests
**How to avoid:** Use `beforeEach(() => { vi.clearAllMocks(); })` and cleanup already configured in setup.ts
**Warning signs:** Tests pass individually but fail when run together

### Pitfall 4: Testing Component Text with Exact Case
**What goes wrong:** Tests fail because component capitalizes text differently
**Why it happens:** SeverityBadge displays "Critical" not "critical"
**How to avoid:** Use case-insensitive matchers: `screen.getByText(/critical/i)`
**Warning signs:** "Unable to find element" when text is clearly visible in error output

### Pitfall 5: Not Mocking Fetch Before Render
**What goes wrong:** Tests use real network calls or undefined fetch
**Why it happens:** CustomerProvider calls fetch on mount
**How to avoid:** Set up `(globalThis as any).fetch = vi.fn()...` BEFORE calling render()
**Warning signs:** Network errors in tests, slow test execution

## Code Examples

Verified patterns from official sources and existing codebase:

### Testing hasSpecialty Function
```typescript
// Source: Existing test from CustomerContext.test.tsx
describe('hasSpecialty', () => {
  it('returns true for enabled specialty', async () => {
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockCustomer),
    });

    const { result } = renderHook(() => useCustomer(), { wrapper });

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.hasSpecialty('DIALYSIS')).toBe(true);
  });

  it('is case-insensitive', async () => {
    // ... setup
    expect(result.current.hasSpecialty('dialysis')).toBe(true);
    expect(result.current.hasSpecialty('Dialysis')).toBe(true);
  });
});
```

### Testing SpecialtyRoute Redirect
```typescript
// Source: Testing Library React Router example
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { CustomerProvider } from '@/contexts/CustomerContext';
import { SpecialtyRoute } from '@/components/guards/SpecialtyRoute';

const mockCustomerWithDialysis = {
  id: 1,
  name: 'Test',
  specialty_type: 'DIALYSIS',
  specialty_modules: [{ id: 1, specialty: 'DIALYSIS', enabled: true, enabled_at: '2024-01-01', is_primary: true }],
  enabled_specialties: ['DIALYSIS'],
};

describe('SpecialtyRoute', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    localStorage.setItem('upstream_access_token', 'test-token');
  });

  it('renders children when specialty is enabled', async () => {
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockCustomerWithDialysis),
    });

    render(
      <MemoryRouter initialEntries={['/specialty/dialysis']}>
        <CustomerProvider>
          <Routes>
            <Route
              path="/specialty/dialysis"
              element={
                <SpecialtyRoute specialty="DIALYSIS">
                  <div>Dialysis Content</div>
                </SpecialtyRoute>
              }
            />
          </Routes>
        </CustomerProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Dialysis Content')).toBeInTheDocument();
    });
  });

  it('redirects to fallback when specialty not enabled', async () => {
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockCustomerWithDialysis), // Only has DIALYSIS
    });

    render(
      <MemoryRouter initialEntries={['/specialty/aba']}>
        <CustomerProvider>
          <Routes>
            <Route path="/dashboard" element={<div>Dashboard Fallback</div>} />
            <Route
              path="/specialty/aba"
              element={
                <SpecialtyRoute specialty="ABA">
                  <div>ABA Content</div>
                </SpecialtyRoute>
              }
            />
          </Routes>
        </CustomerProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Dashboard Fallback')).toBeInTheDocument();
    });
    expect(screen.queryByText('ABA Content')).not.toBeInTheDocument();
  });
});
```

### Testing SpecialtyModulesCard Toggle
```typescript
// Source: Pattern from ActionToggle.test.tsx and CustomerContext patterns
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CustomerProvider } from '@/contexts/CustomerContext';
import { Settings } from '@/pages/Settings';

describe('SpecialtyModulesCard', () => {
  const user = userEvent.setup();

  it('shows toggle switch for each specialty', async () => {
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockCustomer),
    });

    render(
      <CustomerProvider>
        <Settings />
      </CustomerProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Specialty Modules')).toBeInTheDocument();
    });

    // Check all specialty labels appear
    expect(screen.getByText('Dialysis')).toBeInTheDocument();
    expect(screen.getByText('ABA Therapy')).toBeInTheDocument();
  });

  it('disables toggle for primary specialty', async () => {
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockCustomer), // DIALYSIS is primary
    });

    render(
      <CustomerProvider>
        <Settings />
      </CustomerProvider>
    );

    await waitFor(() => {
      const dialysisSwitch = screen.getByRole('switch', { name: /toggle dialysis/i });
      expect(dialysisSwitch).toBeDisabled();
    });
  });
});
```

### Testing Sidebar Dynamic Navigation
```typescript
// Source: MemoryRouter pattern + existing test patterns
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { CustomerProvider } from '@/contexts/CustomerContext';
import { Sidebar } from '@/components/layout/Sidebar';

describe('Sidebar', () => {
  it('shows specialty nav items for enabled specialties', async () => {
    const customerWithABA = {
      ...mockCustomer,
      enabled_specialties: ['DIALYSIS', 'ABA'],
    };

    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(customerWithABA),
    });

    render(
      <MemoryRouter>
        <CustomerProvider>
          <Sidebar isOpen={true} onClose={() => {}} />
        </CustomerProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Dialysis')).toBeInTheDocument();
      expect(screen.getByText('ABA Tracking')).toBeInTheDocument();
      expect(screen.getByText('Authorizations')).toBeInTheDocument();
    });
  });

  it('hides specialty nav when not enabled', async () => {
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockCustomer), // Only DIALYSIS
    });

    render(
      <MemoryRouter>
        <CustomerProvider>
          <Sidebar isOpen={true} onClose={() => {}} />
        </CustomerProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Dialysis')).toBeInTheDocument();
    });
    expect(screen.queryByText('ABA Tracking')).not.toBeInTheDocument();
  });
});
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Jest | Vitest | 2023-2024 | 10-20x faster, native ESM |
| Enzyme | React Testing Library | 2020+ | Tests user behavior, not implementation |
| Istanbul coverage | V8 coverage | Vitest 3.2+ | AST-based accuracy, same speed |
| Mocking useNavigate | MemoryRouter wrapper | RTL best practice | Full router behavior without mocks |

**Deprecated/outdated:**
- Enzyme: React 18+ incompatible, tests implementation details
- shallow rendering: Doesn't test integration, RTL doesn't support it
- `waitForDomChange`: Replaced by `waitFor`

## Open Questions

Things that couldn't be fully resolved:

1. **Coverage threshold enforcement**
   - What we know: Vitest supports per-file thresholds via `coverage.thresholds`
   - What's unclear: Should phase enforce 80% globally or per-file for specialty modules?
   - Recommendation: Start with per-file thresholds on the specific components

2. **Existing test failures**
   - What we know: 8 tests failing in SeverityBadge.test.tsx and AlertsTable.test.tsx (case sensitivity)
   - What's unclear: Whether to fix these as part of this phase
   - Recommendation: Fix them - they're blocking accurate coverage measurement

## Sources

### Primary (HIGH confidence)
- Existing `CustomerContext.test.tsx` - Verified working patterns
- [Testing Library Context Example](https://testing-library.com/docs/example-react-context/) - Custom render pattern
- [Testing Library React Router Example](https://testing-library.com/docs/example-react-router/) - MemoryRouter pattern
- [Vitest Coverage Guide](https://vitest.dev/guide/coverage) - V8 configuration

### Secondary (MEDIUM confidence)
- Project `vitest.config.ts` - Existing configuration
- Project `package.json` - Library versions confirmed

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries already in use, versions verified in package.json
- Architecture patterns: HIGH - Patterns verified from existing CustomerContext.test.tsx
- Pitfalls: HIGH - Based on existing test failures and official documentation

**Research date:** 2026-02-02
**Valid until:** 2026-03-02 (30 days - stable testing ecosystem)
