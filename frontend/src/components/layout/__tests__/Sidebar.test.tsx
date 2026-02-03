/**
 * Tests for Sidebar component dynamic navigation based on enabled specialties.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Sidebar } from '../Sidebar';
import { CustomerProvider, type CustomerProfile } from '@/contexts/CustomerContext';

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

// Mock customer data configurations
const mockCustomerDialysisOnly: CustomerProfile = {
  id: 1,
  name: 'Dialysis Center',
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

const mockCustomerABAOnly: CustomerProfile = {
  id: 2,
  name: 'ABA Therapy Center',
  specialty_type: 'ABA',
  specialty_modules: [
    {
      id: 1,
      specialty: 'ABA',
      enabled: true,
      enabled_at: '2024-01-01T00:00:00Z',
      is_primary: true,
    },
  ],
  enabled_specialties: ['ABA'],
};

const mockCustomerMultiple: CustomerProfile = {
  id: 3,
  name: 'Multi-Specialty Provider',
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
    {
      id: 3,
      specialty: 'IMAGING',
      enabled: true,
      enabled_at: '2024-01-03T00:00:00Z',
      is_primary: false,
    },
  ],
  enabled_specialties: ['DIALYSIS', 'ABA', 'IMAGING'],
};

const mockCustomerABAAndHomeHealth: CustomerProfile = {
  id: 4,
  name: 'Combined Provider',
  specialty_type: 'ABA',
  specialty_modules: [
    {
      id: 1,
      specialty: 'ABA',
      enabled: true,
      enabled_at: '2024-01-01T00:00:00Z',
      is_primary: true,
    },
    {
      id: 2,
      specialty: 'HOME_HEALTH',
      enabled: true,
      enabled_at: '2024-01-02T00:00:00Z',
      is_primary: false,
    },
  ],
  enabled_specialties: ['ABA', 'HOME_HEALTH'],
};

const mockCustomerNoSpecialties: CustomerProfile = {
  id: 5,
  name: 'Basic Provider',
  specialty_type: 'DIALYSIS',
  specialty_modules: [],
  enabled_specialties: [],
};

// Test wrapper
function TestWrapper({ children }: { children: React.ReactNode }) {
  return (
    <MemoryRouter>
      <CustomerProvider>{children}</CustomerProvider>
    </MemoryRouter>
  );
}

describe('Sidebar', () => {
  const mockOnClose = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    localStorage.setItem('upstream_access_token', 'test-token');
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('core navigation', () => {
    it('shows core nav items always', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomerDialysisOnly),
      });

      render(
        <TestWrapper>
          <Sidebar isOpen={true} onClose={mockOnClose} />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Dashboard')).toBeInTheDocument();
      });

      // Core navigation items
      expect(screen.getByText('Claim Scores')).toBeInTheDocument();
      expect(screen.getByText('Work Queue')).toBeInTheDocument();
      expect(screen.getByText('Alerts')).toBeInTheDocument();
      expect(screen.getByText('Execution Log')).toBeInTheDocument();
      expect(screen.getByText('Settings')).toBeInTheDocument();
    });
  });

  describe('specialty navigation visibility', () => {
    it('shows Dialysis nav item when DIALYSIS is enabled', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomerDialysisOnly),
      });

      render(
        <TestWrapper>
          <Sidebar isOpen={true} onClose={mockOnClose} />
        </TestWrapper>
      );

      // Wait for customer name to confirm data loaded
      await waitFor(() => {
        expect(screen.getByText('Dialysis Center')).toBeInTheDocument();
      });

      // Now check for the Dialysis nav item (distinct from header label)
      // The nav item will be in the nav list
      const navLinks = screen.getAllByRole('link');
      const dialysisLink = navLinks.find(link => link.textContent?.includes('Dialysis') && link.getAttribute('href') === '/specialty/dialysis');
      expect(dialysisLink).toBeDefined();
    });

    it('shows ABA nav items when ABA is enabled', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomerABAOnly),
      });

      render(
        <TestWrapper>
          <Sidebar isOpen={true} onClose={mockOnClose} />
        </TestWrapper>
      );

      // Wait for customer name to confirm data loaded
      await waitFor(() => {
        expect(screen.getByText('ABA Therapy Center')).toBeInTheDocument();
      });

      expect(screen.getByText('Authorizations')).toBeInTheDocument();
      expect(screen.getByText('ABA Tracking')).toBeInTheDocument();
    });

    it('hides specialty nav items for disabled specialties', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomerDialysisOnly),
      });

      render(
        <TestWrapper>
          <Sidebar isOpen={true} onClose={mockOnClose} />
        </TestWrapper>
      );

      // Wait for customer name to confirm data loaded
      await waitFor(() => {
        expect(screen.getByText('Dialysis Center')).toBeInTheDocument();
      });

      // ABA items should not be visible
      expect(screen.queryByText('ABA Tracking')).not.toBeInTheDocument();
      // Authorizations should not be visible (belongs to ABA and HOME_HEALTH)
      expect(screen.queryByText('Authorizations')).not.toBeInTheDocument();
      // Imaging PA should not be visible
      expect(screen.queryByText('Imaging PA')).not.toBeInTheDocument();
      // Home Health should not be visible
      expect(screen.queryByText('Home Health')).not.toBeInTheDocument();
      // PT/OT should not be visible
      expect(screen.queryByText('PT/OT')).not.toBeInTheDocument();
    });

    it('shows multiple specialty nav items when multiple specialties enabled', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomerMultiple),
      });

      render(
        <TestWrapper>
          <Sidebar isOpen={true} onClose={mockOnClose} />
        </TestWrapper>
      );

      // Wait for customer name to confirm data loaded
      await waitFor(() => {
        expect(screen.getByText('Multi-Specialty Provider')).toBeInTheDocument();
      });

      // Multiple specialty items
      expect(screen.getByText('ABA Tracking')).toBeInTheDocument();
      expect(screen.getByText('Authorizations')).toBeInTheDocument();
      expect(screen.getByText('Imaging PA')).toBeInTheDocument();
    });
  });

  describe('navigation deduplication', () => {
    it('deduplicates nav items when multiple specialties share same route', async () => {
      // ABA and HOME_HEALTH both have /authorizations route
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomerABAAndHomeHealth),
      });

      render(
        <TestWrapper>
          <Sidebar isOpen={true} onClose={mockOnClose} />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Authorizations')).toBeInTheDocument();
      });

      // Should only appear once even though both ABA and HOME_HEALTH have it
      const authorizationsLinks = screen.getAllByText('Authorizations');
      expect(authorizationsLinks).toHaveLength(1);
    });
  });

  describe('header display', () => {
    it('shows customer name in header', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomerDialysisOnly),
      });

      render(
        <TestWrapper>
          <Sidebar isOpen={true} onClose={mockOnClose} />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Dialysis Center')).toBeInTheDocument();
      });
    });

    it('shows primary specialty label in header', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomerABAOnly),
      });

      render(
        <TestWrapper>
          <Sidebar isOpen={true} onClose={mockOnClose} />
        </TestWrapper>
      );

      await waitFor(() => {
        // The specialty label should appear in the header
        expect(screen.getByText('ABA Therapy')).toBeInTheDocument();
      });
    });

    it('shows fallback name when no customer loaded', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: false,
        status: 401,
        statusText: 'Unauthorized',
      });

      render(
        <TestWrapper>
          <Sidebar isOpen={true} onClose={mockOnClose} customerName="Fallback Name" />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Fallback Name')).toBeInTheDocument();
      });
    });
  });

  describe('loading state', () => {
    it('shows loading skeleton when customer data loading', async () => {
      // Never resolve to keep in loading state
      (globalThis as any).fetch = vi.fn().mockImplementation(
        () => new Promise(() => {})
      );

      render(
        <TestWrapper>
          <Sidebar isOpen={true} onClose={mockOnClose} />
        </TestWrapper>
      );

      // Should show skeleton items
      const skeletons = document.querySelectorAll('.skeleton');
      expect(skeletons.length).toBeGreaterThan(0);
    });
  });

  describe('active modules indicator', () => {
    it('shows active modules indicator when >1 specialty enabled', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomerMultiple),
      });

      render(
        <TestWrapper>
          <Sidebar isOpen={true} onClose={mockOnClose} />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Active modules:')).toBeInTheDocument();
      });
    });

    it('does not show active modules indicator when only 1 specialty enabled', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomerDialysisOnly),
      });

      render(
        <TestWrapper>
          <Sidebar isOpen={true} onClose={mockOnClose} />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Dashboard')).toBeInTheDocument();
      });

      expect(screen.queryByText('Active modules:')).not.toBeInTheDocument();
    });
  });

  describe('sidebar visibility', () => {
    it('is visible when isOpen is true', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomerDialysisOnly),
      });

      render(
        <TestWrapper>
          <Sidebar isOpen={true} onClose={mockOnClose} />
        </TestWrapper>
      );

      await waitFor(() => {
        const sidebar = screen.getByRole('navigation', { name: 'Main navigation' });
        expect(sidebar).toBeInTheDocument();
      });
    });
  });
});
