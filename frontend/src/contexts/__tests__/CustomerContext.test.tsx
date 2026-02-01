/**
 * Tests for CustomerContext provider and useCustomer hook.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import {
  CustomerProvider,
  useCustomer,
  type CustomerProfile,
  type SpecialtyType,
} from '../CustomerContext';

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

// Mock customer data
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

// Helper to create a wrapper component
const wrapper = ({ children }: { children: React.ReactNode }) => (
  <CustomerProvider>{children}</CustomerProvider>
);

describe('CustomerContext', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    localStorage.setItem('upstream_access_token', 'test-token');
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('CustomerProvider', () => {
    it('loads customer on mount', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomer),
      });

      const { result } = renderHook(() => useCustomer(), { wrapper });

      // Initially loading
      expect(result.current.loading).toBe(true);

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current.customer).toEqual(mockCustomer);
      expect(result.current.error).toBeNull();
    });

    it('handles fetch error gracefully', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
      });

      const { result } = renderHook(() => useCustomer(), { wrapper });

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current.customer).toBeNull();
      expect(result.current.error).toContain('Failed to fetch customer');
    });

    it('handles 401 without setting error', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: false,
        status: 401,
        statusText: 'Unauthorized',
      });

      const { result } = renderHook(() => useCustomer(), { wrapper });

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current.customer).toBeNull();
      expect(result.current.error).toBeNull();
    });
  });

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

    it('returns false for non-enabled specialty', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomer),
      });

      const { result } = renderHook(() => useCustomer(), { wrapper });

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current.hasSpecialty('ABA')).toBe(false);
      expect(result.current.hasSpecialty('IMAGING')).toBe(false);
    });

    it('is case-insensitive', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomer),
      });

      const { result } = renderHook(() => useCustomer(), { wrapper });

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current.hasSpecialty('dialysis')).toBe(true);
      expect(result.current.hasSpecialty('Dialysis')).toBe(true);
    });

    it('returns false when no customer loaded', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: false,
        status: 401,
        statusText: 'Unauthorized',
      });

      const { result } = renderHook(() => useCustomer(), { wrapper });

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current.hasSpecialty('DIALYSIS')).toBe(false);
    });
  });

  describe('enableSpecialty', () => {
    it('updates state optimistically', async () => {
      const updatedCustomer: CustomerProfile = {
        ...mockCustomer,
        enabled_specialties: ['DIALYSIS', 'ABA'],
        specialty_modules: [
          ...mockCustomer.specialty_modules,
          {
            id: 2,
            specialty: 'ABA',
            enabled: true,
            enabled_at: '2024-01-02T00:00:00Z',
            is_primary: false,
          },
        ],
      };

      (globalThis as any).fetch = vi
        .fn()
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve(mockCustomer),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve(updatedCustomer),
        });

      const { result } = renderHook(() => useCustomer(), { wrapper });

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      // Enable ABA
      await act(async () => {
        await result.current.enableSpecialty('ABA');
      });

      expect(result.current.hasSpecialty('ABA')).toBe(true);
    });

    it('rolls back on API error', async () => {
      (globalThis as any).fetch = vi
        .fn()
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve(mockCustomer),
        })
        .mockResolvedValueOnce({
          ok: false,
          json: () => Promise.resolve({ error: 'Failed to enable' }),
        });

      const { result } = renderHook(() => useCustomer(), { wrapper });

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      // Try to enable ABA (should fail)
      await act(async () => {
        try {
          await result.current.enableSpecialty('ABA');
        } catch {
          // Expected
        }
      });

      // Should rollback
      expect(result.current.hasSpecialty('ABA')).toBe(false);
    });

    it('throws when no customer loaded', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: false,
        status: 401,
        statusText: 'Unauthorized',
      });

      const { result } = renderHook(() => useCustomer(), { wrapper });

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      await expect(result.current.enableSpecialty('ABA')).rejects.toThrow('No customer loaded');
    });
  });

  describe('disableSpecialty', () => {
    it('removes specialty from enabled list', async () => {
      const customerWithABA: CustomerProfile = {
        ...mockCustomer,
        enabled_specialties: ['DIALYSIS', 'ABA'],
        specialty_modules: [
          ...mockCustomer.specialty_modules,
          {
            id: 2,
            specialty: 'ABA',
            enabled: true,
            enabled_at: '2024-01-02T00:00:00Z',
            is_primary: false,
          },
        ],
      };

      const customerAfterDisable: CustomerProfile = {
        ...mockCustomer,
        enabled_specialties: ['DIALYSIS'],
        specialty_modules: [
          ...mockCustomer.specialty_modules,
          {
            id: 2,
            specialty: 'ABA',
            enabled: false,
            enabled_at: '2024-01-02T00:00:00Z',
            is_primary: false,
          },
        ],
      };

      (globalThis as any).fetch = vi
        .fn()
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve(customerWithABA),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve(customerAfterDisable),
        });

      const { result } = renderHook(() => useCustomer(), { wrapper });

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current.hasSpecialty('ABA')).toBe(true);

      // Disable ABA
      await act(async () => {
        await result.current.disableSpecialty('ABA');
      });

      expect(result.current.hasSpecialty('ABA')).toBe(false);
    });

    it('throws when trying to disable primary specialty', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomer),
      });

      const { result } = renderHook(() => useCustomer(), { wrapper });

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      // Try to disable primary specialty
      await expect(result.current.disableSpecialty('DIALYSIS' as SpecialtyType)).rejects.toThrow(
        'Cannot disable primary specialty'
      );
    });
  });

  describe('refreshCustomer', () => {
    it('refetches customer data', async () => {
      const updatedCustomer: CustomerProfile = {
        ...mockCustomer,
        name: 'Updated Customer',
      };

      (globalThis as any).fetch = vi
        .fn()
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve(mockCustomer),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve(updatedCustomer),
        });

      const { result } = renderHook(() => useCustomer(), { wrapper });

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current.customer?.name).toBe('Test Customer');

      // Refresh
      await act(async () => {
        await result.current.refreshCustomer();
      });

      expect(result.current.customer?.name).toBe('Updated Customer');
    });
  });

  describe('useCustomer hook', () => {
    it('throws when used outside provider', () => {
      // Suppress console.error for this test
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      expect(() => {
        renderHook(() => useCustomer());
      }).toThrow('useCustomer must be used within a CustomerProvider');

      consoleSpy.mockRestore();
    });
  });
});
