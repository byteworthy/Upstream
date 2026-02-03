/**
 * Tests for Settings page, focusing on SpecialtyModulesCard toggle functionality.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { Settings } from '../Settings';
import { CustomerProvider, type CustomerProfile } from '@/contexts/CustomerContext';

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}));

// Mock customer data
const mockCustomerDialysisPrimary: CustomerProfile = {
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

// Test wrapper
function TestWrapper({ children }: { children: React.ReactNode }) {
  return (
    <MemoryRouter>
      <CustomerProvider>{children}</CustomerProvider>
    </MemoryRouter>
  );
}

describe('Settings', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    localStorage.setItem('upstream_access_token', 'test-token');
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('SpecialtyModulesCard - loading state', () => {
    it('shows loading spinner while customer data loads', async () => {
      // Keep fetch pending to simulate loading
      (globalThis as any).fetch = vi.fn().mockImplementation(
        () => new Promise(() => {})
      );

      render(
        <TestWrapper>
          <Settings />
        </TestWrapper>
      );

      // Should show loading state in the specialty modules card
      expect(screen.getByText('Loading specialty configuration...')).toBeInTheDocument();
    });
  });

  describe('SpecialtyModulesCard - specialty display', () => {
    it('displays all 5 specialty modules', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomerDialysisPrimary),
      });

      render(
        <TestWrapper>
          <Settings />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Specialty Modules')).toBeInTheDocument();
      });

      // All 5 specialty modules should be displayed
      expect(screen.getByText('Dialysis')).toBeInTheDocument();
      expect(screen.getByText('ABA Therapy')).toBeInTheDocument();
      expect(screen.getByText('Imaging')).toBeInTheDocument();
      expect(screen.getByText('Home Health')).toBeInTheDocument();
      expect(screen.getByText('PT/OT')).toBeInTheDocument();
    });

    it('shows "Primary" badge next to primary specialty', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomerDialysisPrimary),
      });

      render(
        <TestWrapper>
          <Settings />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Primary')).toBeInTheDocument();
      });
    });
  });

  describe('SpecialtyModulesCard - toggle states', () => {
    it('toggle switch is disabled for primary specialty', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomerDialysisPrimary),
      });

      render(
        <TestWrapper>
          <Settings />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Specialty Modules')).toBeInTheDocument();
      });

      // Find the Dialysis toggle (primary) - should be disabled
      const dialysisToggle = screen.getByRole('switch', { name: /toggle dialysis/i });
      expect(dialysisToggle).toBeDisabled();
    });

    it('toggle switch is enabled (checked) for enabled specialties', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomerWithMultiple),
      });

      render(
        <TestWrapper>
          <Settings />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Specialty Modules')).toBeInTheDocument();
      });

      // Find the ABA toggle - should be checked (enabled)
      const abaToggle = screen.getByRole('switch', { name: /toggle aba therapy/i });
      expect(abaToggle).toBeChecked();
    });

    it('toggle switch is unchecked for non-enabled specialties', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomerDialysisPrimary),
      });

      render(
        <TestWrapper>
          <Settings />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Specialty Modules')).toBeInTheDocument();
      });

      // Find the Imaging toggle - should be unchecked (not enabled)
      const imagingToggle = screen.getByRole('switch', { name: /toggle imaging/i });
      expect(imagingToggle).not.toBeChecked();
    });
  });

  describe('SpecialtyModulesCard - toggle interactions', () => {
    it('clicking toggle calls enableSpecialty when turning on', async () => {
      const user = userEvent.setup();

      const enabledCustomer: CustomerProfile = {
        ...mockCustomerDialysisPrimary,
        enabled_specialties: ['DIALYSIS', 'IMAGING'],
        specialty_modules: [
          ...mockCustomerDialysisPrimary.specialty_modules,
          {
            id: 3,
            specialty: 'IMAGING',
            enabled: true,
            enabled_at: '2024-01-03T00:00:00Z',
            is_primary: false,
          },
        ],
      };

      (globalThis as any).fetch = vi
        .fn()
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve(mockCustomerDialysisPrimary),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve(enabledCustomer),
        });

      render(
        <TestWrapper>
          <Settings />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Specialty Modules')).toBeInTheDocument();
      });

      // Find the Imaging toggle and click it
      const imagingToggle = screen.getByRole('switch', { name: /toggle imaging/i });
      await user.click(imagingToggle);

      // Verify API was called
      await waitFor(() => {
        expect((globalThis as any).fetch).toHaveBeenCalledTimes(2);
      });

      // Check second call was to enable specialty endpoint
      const secondCall = (globalThis as any).fetch.mock.calls[1];
      expect(secondCall[0]).toContain('/customers/enable_specialty/');
      expect(secondCall[1].method).toBe('POST');
    });

    it('clicking toggle calls disableSpecialty when turning off', async () => {
      const user = userEvent.setup();

      const disabledCustomer: CustomerProfile = {
        ...mockCustomerWithMultiple,
        enabled_specialties: ['DIALYSIS'],
        specialty_modules: [
          mockCustomerWithMultiple.specialty_modules[0],
          {
            ...mockCustomerWithMultiple.specialty_modules[1],
            enabled: false,
          },
        ],
      };

      (globalThis as any).fetch = vi
        .fn()
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve(mockCustomerWithMultiple),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve(disabledCustomer),
        });

      render(
        <TestWrapper>
          <Settings />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Specialty Modules')).toBeInTheDocument();
      });

      // Find the ABA toggle and click it to disable
      const abaToggle = screen.getByRole('switch', { name: /toggle aba therapy/i });
      await user.click(abaToggle);

      // Verify API was called
      await waitFor(() => {
        expect((globalThis as any).fetch).toHaveBeenCalledTimes(2);
      });

      // Check second call was to disable specialty endpoint
      const secondCall = (globalThis as any).fetch.mock.calls[1];
      expect(secondCall[0]).toContain('/customers/disable_specialty/');
      expect(secondCall[1].method).toBe('POST');
    });
  });

  describe('SpecialtyModulesCard - error handling', () => {
    it('handles API error gracefully with rollback', async () => {
      const user = userEvent.setup();

      (globalThis as any).fetch = vi
        .fn()
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve(mockCustomerDialysisPrimary),
        })
        .mockResolvedValueOnce({
          ok: false,
          json: () => Promise.resolve({ error: 'Failed to enable specialty' }),
        });

      render(
        <TestWrapper>
          <Settings />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Specialty Modules')).toBeInTheDocument();
      });

      // Find the Imaging toggle and click it
      const imagingToggle = screen.getByRole('switch', { name: /toggle imaging/i });
      const initialChecked = imagingToggle.getAttribute('aria-checked');

      await user.click(imagingToggle);

      // Wait for the API call to complete and rollback
      await waitFor(() => {
        // Toggle should rollback to original state
        expect(imagingToggle.getAttribute('aria-checked')).toBe(initialChecked);
      });
    });
  });

  describe('Settings - general UI', () => {
    it('renders Settings page header with "Automation Settings" title', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomerDialysisPrimary),
      });

      render(
        <TestWrapper>
          <Settings />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Automation Settings')).toBeInTheDocument();
      });
    });

    it('shows automation stage selector', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomerDialysisPrimary),
      });

      render(
        <TestWrapper>
          <Settings />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Automation Stage')).toBeInTheDocument();
      });
    });

    it('shows confidence threshold sliders', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomerDialysisPrimary),
      });

      render(
        <TestWrapper>
          <Settings />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Confidence Thresholds')).toBeInTheDocument();
      });
    });

    it('shows action toggles section', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomerDialysisPrimary),
      });

      render(
        <TestWrapper>
          <Settings />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Enabled Actions')).toBeInTheDocument();
      });
    });

    it('shows Reset to Defaults button', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomerDialysisPrimary),
      });

      render(
        <TestWrapper>
          <Settings />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Reset to Defaults')).toBeInTheDocument();
      });
    });

    it('shows amount thresholds section', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomerDialysisPrimary),
      });

      render(
        <TestWrapper>
          <Settings />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Amount Thresholds')).toBeInTheDocument();
      });
    });
  });
});
