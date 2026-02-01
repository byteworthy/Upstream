import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { AlertsTable } from './AlertsTable';

const mockAlerts = [
  {
    id: 1,
    title: 'High denial rate detected',
    severity: 'high' as const,
    alert_type: 'threshold' as const,
    status: 'open' as const,
    claim_id: 1001,
    claim_score_id: 1,
    payload: {},
    resolved_at: null,
    resolved_by_id: null,
    resolution_notes: null,
    created_at: '2024-01-15T10:00:00Z',
    updated_at: '2024-01-15T10:00:00Z',
  },
  {
    id: 2,
    title: 'Duplicate claim submitted',
    severity: 'medium' as const,
    alert_type: 'anomaly' as const,
    status: 'acknowledged' as const,
    claim_id: 1002,
    claim_score_id: 2,
    payload: {},
    resolved_at: null,
    resolved_by_id: null,
    resolution_notes: null,
    created_at: '2024-01-14T09:00:00Z',
    updated_at: '2024-01-14T09:00:00Z',
  },
];

const renderWithRouter = (component: React.ReactNode) => {
  return render(<MemoryRouter>{component}</MemoryRouter>);
};

describe('AlertsTable', () => {
  it('renders alert data correctly', () => {
    renderWithRouter(<AlertsTable alerts={mockAlerts} />);

    expect(screen.getByText('High denial rate detected')).toBeInTheDocument();
    expect(screen.getByText('Duplicate claim submitted')).toBeInTheDocument();
  });

  it('shows severity badges', () => {
    renderWithRouter(<AlertsTable alerts={mockAlerts} />);

    expect(screen.getByText('high')).toBeInTheDocument();
    expect(screen.getByText('medium')).toBeInTheDocument();
  });

  it('shows status for each alert', () => {
    renderWithRouter(<AlertsTable alerts={mockAlerts} />);

    expect(screen.getByText('open')).toBeInTheDocument();
    expect(screen.getByText('acknowledged')).toBeInTheDocument();
  });

  it('shows alert type', () => {
    renderWithRouter(<AlertsTable alerts={mockAlerts} />);

    expect(screen.getByText('threshold')).toBeInTheDocument();
    expect(screen.getByText('anomaly')).toBeInTheDocument();
  });

  it('shows empty state when no alerts', () => {
    renderWithRouter(<AlertsTable alerts={[]} />);

    expect(screen.getByText('No alerts found')).toBeInTheDocument();
  });

  it('calls onSort when clicking sortable column', async () => {
    const user = userEvent.setup();
    const onSort = vi.fn();
    renderWithRouter(<AlertsTable alerts={mockAlerts} onSort={onSort} />);

    const titleHeader = screen.getByText('Title');
    await user.click(titleHeader);

    expect(onSort).toHaveBeenCalledWith('title');
  });

  it('shows loading state', () => {
    renderWithRouter(<AlertsTable alerts={[]} loading />);

    // Check for loading skeleton elements
    const skeletons = document.querySelectorAll('.animate-pulse');
    expect(skeletons.length).toBeGreaterThan(0);
  });
});
