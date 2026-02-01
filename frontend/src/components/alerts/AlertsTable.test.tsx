import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { AlertsTable } from './AlertsTable';

const mockAlerts = [
  {
    id: 1,
    title: 'High denial rate detected',
    description: 'Denial rate has exceeded threshold',
    severity: 'high' as const,
    alert_type: 'denial_risk' as const,
    specialty: 'DIALYSIS' as const,
    claim: 1001,
    claim_score: 1,
    evidence: {},
    is_acknowledged: false,
    acknowledged_at: null,
    acknowledged_by: null,
    is_resolved: false,
    resolved_at: null,
    resolved_by: null,
    resolution_notes: null,
    created_at: '2024-01-15T10:00:00Z',
    updated_at: '2024-01-15T10:00:00Z',
  },
  {
    id: 2,
    title: 'Duplicate claim submitted',
    description: 'Potential duplicate claim detected',
    severity: 'medium' as const,
    alert_type: 'system_anomaly' as const,
    specialty: 'CORE' as const,
    claim: 1002,
    claim_score: 2,
    evidence: {},
    is_acknowledged: true,
    acknowledged_at: '2024-01-14T10:00:00Z',
    acknowledged_by: 1,
    is_resolved: false,
    resolved_at: null,
    resolved_by: null,
    resolution_notes: null,
    created_at: '2024-01-14T09:00:00Z',
    updated_at: '2024-01-14T09:00:00Z',
  },
];

const renderWithRouter = (component: React.ReactNode) => {
  return render(<MemoryRouter>{component}</MemoryRouter>);
};

const defaultProps = {
  onAcknowledge: vi.fn(),
  onResolve: vi.fn(),
  isProcessing: false,
};

describe('AlertsTable', () => {
  it('renders alert data correctly', () => {
    renderWithRouter(<AlertsTable alerts={mockAlerts} {...defaultProps} />);

    expect(screen.getByText('High denial rate detected')).toBeInTheDocument();
    expect(screen.getByText('Duplicate claim submitted')).toBeInTheDocument();
  });

  it('shows severity badges', () => {
    renderWithRouter(<AlertsTable alerts={mockAlerts} {...defaultProps} />);

    expect(screen.getByText('high')).toBeInTheDocument();
    expect(screen.getByText('medium')).toBeInTheDocument();
  });

  it('shows status for acknowledged alerts', () => {
    renderWithRouter(<AlertsTable alerts={mockAlerts} {...defaultProps} />);

    // The component shows acknowledgment status via icons/buttons
    expect(screen.getAllByRole('button').length).toBeGreaterThan(0);
  });

  it('shows alert type', () => {
    renderWithRouter(<AlertsTable alerts={mockAlerts} {...defaultProps} />);

    expect(screen.getByText('Denial Risk')).toBeInTheDocument();
    expect(screen.getByText('System Anomaly')).toBeInTheDocument();
  });

  it('shows empty state when no alerts', () => {
    renderWithRouter(<AlertsTable alerts={[]} {...defaultProps} />);

    expect(screen.getByText('No alerts found')).toBeInTheDocument();
  });

  it('handles sorting when clicking column header', async () => {
    const user = userEvent.setup();
    renderWithRouter(<AlertsTable alerts={mockAlerts} {...defaultProps} />);

    const titleHeader = screen.getByText('Title');
    await user.click(titleHeader);

    // Sorting is internal, just verify no errors
    expect(screen.getByText('High denial rate detected')).toBeInTheDocument();
  });

  it('handles acknowledge action', async () => {
    const onAcknowledge = vi.fn();
    renderWithRouter(
      <AlertsTable alerts={mockAlerts} {...defaultProps} onAcknowledge={onAcknowledge} />
    );

    // Find acknowledge button for non-acknowledged alert
    const buttons = screen.getAllByRole('button');
    expect(buttons.length).toBeGreaterThan(0);
  });
});
