import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SeverityBadge } from './SeverityBadge';

describe('SeverityBadge', () => {
  it('renders critical severity', () => {
    render(<SeverityBadge severity="critical" />);
    expect(screen.getByText('critical')).toBeInTheDocument();
  });

  it('renders high severity', () => {
    render(<SeverityBadge severity="high" />);
    expect(screen.getByText('high')).toBeInTheDocument();
  });

  it('renders medium severity', () => {
    render(<SeverityBadge severity="medium" />);
    expect(screen.getByText('medium')).toBeInTheDocument();
  });

  it('renders low severity', () => {
    render(<SeverityBadge severity="low" />);
    expect(screen.getByText('low')).toBeInTheDocument();
  });

  it('renders info severity', () => {
    render(<SeverityBadge severity="info" />);
    expect(screen.getByText('info')).toBeInTheDocument();
  });

  it('applies correct styling for critical', () => {
    render(<SeverityBadge severity="critical" />);
    const badge = screen.getByText('critical');
    expect(badge.className).toContain('bg-danger');
  });

  it('applies correct styling for info', () => {
    render(<SeverityBadge severity="info" />);
    const badge = screen.getByText('info');
    expect(badge.className).toContain('bg-muted');
  });
});
