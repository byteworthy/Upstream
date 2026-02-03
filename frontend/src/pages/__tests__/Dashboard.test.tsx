/**
 * Tests for Dashboard page, focusing on SpecialtyWidgets conditional rendering.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Dashboard } from '../Dashboard';
import { CustomerProvider, type CustomerProfile } from '@/contexts/CustomerContext';

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

// Mock the dashboardApi
vi.mock('@/lib/api', () => ({
  dashboardApi: {
    getMetrics: vi.fn().mockResolvedValue({
      total_claims: 12847,
      claims_last_30_days: 4532,
      denial_rate: 4.2,
      average_score: 87.3,
      tier_distribution: { tier_1: 3200, tier_2: 980, tier_3: 352 },
      recent_alerts: [],
    }),
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

const mockCustomerAllSpecialties: CustomerProfile = {
  id: 4,
  name: 'Full Provider',
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
    {
      id: 4,
      specialty: 'HOME_HEALTH',
      enabled: true,
      enabled_at: '2024-01-04T00:00:00Z',
      is_primary: false,
    },
    {
      id: 5,
      specialty: 'PTOT',
      enabled: true,
      enabled_at: '2024-01-05T00:00:00Z',
      is_primary: false,
    },
  ],
  enabled_specialties: ['DIALYSIS', 'ABA', 'IMAGING', 'HOME_HEALTH', 'PTOT'],
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

describe('Dashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    localStorage.setItem('upstream_access_token', 'test-token');
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('SpecialtyWidgets - loading state', () => {
    it('shows nothing while customer data is loading', async () => {
      // Never resolve customer fetch to keep in loading state
      (globalThis as any).fetch = vi.fn().mockImplementation(
        () => new Promise(() => {})
      );

      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      );

      // Wait a bit for the component to render
      await waitFor(() => {
        // Dashboard loading text may appear
        expect(screen.queryByText('Specialty Modules')).not.toBeInTheDocument();
      });
    });
  });

  describe('SpecialtyWidgets - empty state', () => {
    it('shows nothing when no specialties are enabled', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomerNoSpecialties),
      });

      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      );

      await waitFor(() => {
        // Dashboard should render
        expect(screen.getByText('Dashboard')).toBeInTheDocument();
      });

      // Specialty Modules heading should not appear
      expect(screen.queryByText('Specialty Modules')).not.toBeInTheDocument();
    });
  });

  describe('SpecialtyWidgets - heading', () => {
    it('shows "Specialty Modules" heading when at least one specialty enabled', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomerDialysisOnly),
      });

      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Specialty Modules')).toBeInTheDocument();
      });
    });
  });

  describe('SpecialtyWidgets - individual specialty widgets', () => {
    it('renders Dialysis widget card when DIALYSIS is enabled', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomerDialysisOnly),
      });

      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Dialysis')).toBeInTheDocument();
      });

      // Should show the description for Dialysis widget
      expect(screen.getByText('MA payment variance and ESRD PPS monitoring')).toBeInTheDocument();
    });

    it('renders ABA Therapy widget card when ABA is enabled', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomerABAOnly),
      });

      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('ABA Therapy')).toBeInTheDocument();
      });

      // Should show the description for ABA widget
      expect(screen.getByText('Authorization cycles and unit exhaustion tracking')).toBeInTheDocument();
    });

    it('renders Imaging widget card when IMAGING is enabled', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomerMultiple),
      });

      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Imaging')).toBeInTheDocument();
      });

      // Should show the description for Imaging widget
      expect(screen.getByText('RBM requirements and AUC compliance')).toBeInTheDocument();
    });

    it('renders Home Health widget card when HOME_HEALTH is enabled', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomerAllSpecialties),
      });

      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Home Health')).toBeInTheDocument();
      });

      // Should show the description for Home Health widget
      expect(screen.getByText('PDGM validation and certification cycles')).toBeInTheDocument();
    });

    it('renders PT/OT widget card when PTOT is enabled', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomerAllSpecialties),
      });

      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('PT/OT')).toBeInTheDocument();
      });

      // Should show the description for PT/OT widget
      expect(screen.getByText('8-minute rule compliance and G-code reporting')).toBeInTheDocument();
    });
  });

  describe('SpecialtyWidgets - multiple specialties', () => {
    it('shows multiple widget cards when multiple specialties enabled', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomerMultiple),
      });

      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Specialty Modules')).toBeInTheDocument();
      });

      // Should show all three enabled specialties
      expect(screen.getByText('Dialysis')).toBeInTheDocument();
      expect(screen.getByText('ABA Therapy')).toBeInTheDocument();
      expect(screen.getByText('Imaging')).toBeInTheDocument();
    });

    it('does not render disabled specialty widgets', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomerDialysisOnly),
      });

      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Dialysis')).toBeInTheDocument();
      });

      // These should NOT be rendered since they're not enabled
      expect(screen.queryByText('ABA Therapy')).not.toBeInTheDocument();
      expect(screen.queryByText('Imaging')).not.toBeInTheDocument();
      expect(screen.queryByText('Home Health')).not.toBeInTheDocument();
      expect(screen.queryByText('PT/OT')).not.toBeInTheDocument();
    });
  });

  describe('Dashboard - core elements', () => {
    it('renders Dashboard title', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomerDialysisOnly),
      });

      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Dashboard' })).toBeInTheDocument();
      });
    });

    it('renders date range selector buttons', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomerDialysisOnly),
      });

      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('7 Days')).toBeInTheDocument();
      });

      expect(screen.getByText('30 Days')).toBeInTheDocument();
      expect(screen.getByText('90 Days')).toBeInTheDocument();
    });

    it('renders metric cards', async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCustomerDialysisOnly),
      });

      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Total Claims')).toBeInTheDocument();
      });

      expect(screen.getByText('Claims This Period')).toBeInTheDocument();
      expect(screen.getByText('Denial Rate')).toBeInTheDocument();
      expect(screen.getByText('Average Score')).toBeInTheDocument();
    });

    it('shows loading state initially', async () => {
      // Delay the customer fetch
      (globalThis as any).fetch = vi.fn().mockImplementation(
        () => new Promise(() => {})
      );

      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      );

      // Should show loading text
      expect(screen.getByText('Loading dashboard...')).toBeInTheDocument();
    });
  });
});
