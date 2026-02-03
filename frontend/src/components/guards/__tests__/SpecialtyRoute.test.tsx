/**
 * Tests for SpecialtyRoute guard component.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { SpecialtyRoute, withSpecialtyGuard } from '../SpecialtyRoute';
import { CustomerProvider, type CustomerProfile } from '@/contexts/CustomerContext';

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

// Mock customer data
const mockCustomerWithDialysis: CustomerProfile = {
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

const mockCustomerWithMultiple: CustomerProfile = {
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
    {
      id: 2,
      specialty: 'ABA',
      enabled: true,
      enabled_at: '2024-01-02T00:00:00Z',
      is_primary: false,
    },
  ],
  enabled_specialties: ['DIALYSIS', 'ABA'],
};

// Test wrapper component
function TestWrapper({
  children,
  initialRoute = '/test',
}: {
  children: React.ReactNode;
  initialRoute?: string;
}) {
  return (
    <MemoryRouter initialEntries={[initialRoute]}>
      <CustomerProvider>{children}</CustomerProvider>
    </MemoryRouter>
  );
}

describe('SpecialtyRoute', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    localStorage.setItem('upstream_access_token', 'test-token');
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('loading state', () => {
    it('shows loading state while customer data loads', async () => {
      // Never resolve to keep in loading state
      (globalThis as any).fetch = vi.fn().mockImplementation(
        () => new Promise(() => {})
      );

      render(
        <TestWrapper>
          <SpecialtyRoute specialty="DIALYSIS">
            <div>Protected Content</div>
          </SpecialtyRoute>
        </TestWrapper>
      );

      expect(screen.getByText('Loading...')).toBeInTheDocument();
      expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
    });
  });

  describe('authorized access', () => {
    it('renders children when customer has required specialty enabled', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomerWithDialysis),
      });

      render(
        <TestWrapper>
          <Routes>
            <Route
              path="/test"
              element={
                <SpecialtyRoute specialty="DIALYSIS">
                  <div>Protected Dialysis Content</div>
                </SpecialtyRoute>
              }
            />
          </Routes>
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Protected Dialysis Content')).toBeInTheDocument();
      });
    });

    it('renders children for any enabled specialty in multi-specialty customer', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomerWithMultiple),
      });

      render(
        <TestWrapper>
          <Routes>
            <Route
              path="/test"
              element={
                <SpecialtyRoute specialty="ABA">
                  <div>Protected ABA Content</div>
                </SpecialtyRoute>
              }
            />
          </Routes>
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Protected ABA Content')).toBeInTheDocument();
      });
    });
  });

  describe('unauthorized redirect', () => {
    it('redirects to default fallback path when specialty not enabled', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomerWithDialysis),
      });

      render(
        <TestWrapper>
          <Routes>
            <Route
              path="/test"
              element={
                <SpecialtyRoute specialty="ABA">
                  <div>Protected ABA Content</div>
                </SpecialtyRoute>
              }
            />
            <Route path="/dashboard" element={<div>Dashboard Fallback</div>} />
          </Routes>
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Dashboard Fallback')).toBeInTheDocument();
      });
      expect(screen.queryByText('Protected ABA Content')).not.toBeInTheDocument();
    });

    it('redirects to custom fallback path when specified', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomerWithDialysis),
      });

      render(
        <TestWrapper>
          <Routes>
            <Route
              path="/test"
              element={
                <SpecialtyRoute specialty="IMAGING" fallbackPath="/settings">
                  <div>Protected Imaging Content</div>
                </SpecialtyRoute>
              }
            />
            <Route path="/settings" element={<div>Settings Fallback</div>} />
          </Routes>
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Settings Fallback')).toBeInTheDocument();
      });
      expect(screen.queryByText('Protected Imaging Content')).not.toBeInTheDocument();
    });
  });

  describe('no customer redirect', () => {
    it('redirects to login when no customer (401 response)', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: false,
        status: 401,
        statusText: 'Unauthorized',
      });

      render(
        <TestWrapper>
          <Routes>
            <Route
              path="/test"
              element={
                <SpecialtyRoute specialty="DIALYSIS">
                  <div>Protected Content</div>
                </SpecialtyRoute>
              }
            />
            <Route path="/login" element={<div>Login Page</div>} />
          </Routes>
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Login Page')).toBeInTheDocument();
      });
      expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
    });
  });

  describe('withSpecialtyGuard HOC', () => {
    it('wraps component correctly with specialty guard', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomerWithDialysis),
      });

      const TestComponent = () => <div>HOC Protected Content</div>;
      const GuardedComponent = withSpecialtyGuard(TestComponent, 'DIALYSIS');

      render(
        <TestWrapper>
          <Routes>
            <Route path="/test" element={<GuardedComponent />} />
          </Routes>
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('HOC Protected Content')).toBeInTheDocument();
      });
    });

    it('HOC redirects when specialty not enabled', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomerWithDialysis),
      });

      const TestComponent = () => <div>HOC Protected Content</div>;
      const GuardedComponent = withSpecialtyGuard(TestComponent, 'ABA', '/custom-fallback');

      render(
        <TestWrapper>
          <Routes>
            <Route path="/test" element={<GuardedComponent />} />
            <Route path="/custom-fallback" element={<div>Custom Fallback</div>} />
          </Routes>
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Custom Fallback')).toBeInTheDocument();
      });
      expect(screen.queryByText('HOC Protected Content')).not.toBeInTheDocument();
    });
  });
});
