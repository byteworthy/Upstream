import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Activity } from 'lucide-react';
import { MetricCard, MetricCardCompact } from './MetricCard';

describe('MetricCard', () => {
  it('renders title and value', () => {
    render(<MetricCard title="Total Claims" value="1,234" />);

    expect(screen.getByText('Total Claims')).toBeInTheDocument();
    expect(screen.getByText('1,234')).toBeInTheDocument();
  });

  it('renders with icon', () => {
    render(<MetricCard title="Active Sessions" value="42" icon={Activity} />);

    expect(screen.getByText('Active Sessions')).toBeInTheDocument();
    expect(screen.getByText('42')).toBeInTheDocument();
  });

  it('shows positive trend correctly', () => {
    render(<MetricCard title="Success Rate" value="98%" trend={{ value: 5.2, isPositive: true }} />);

    expect(screen.getByText('+5.2%')).toBeInTheDocument();
  });

  it('shows negative trend correctly', () => {
    render(<MetricCard title="Errors" value="25" trend={{ value: -5.2, isPositive: false }} />);

    expect(screen.getByText('-5.2%')).toBeInTheDocument();
  });

  it('renders description', () => {
    render(<MetricCard title="Revenue" value="$50,000" description="vs last month" />);

    expect(screen.getByText('vs last month')).toBeInTheDocument();
  });

  it('renders sparkline when provided', () => {
    const { container } = render(
      <MetricCard title="Traffic" value="10K" sparkline={[10, 20, 15, 25, 30, 28]} />
    );

    // Sparkline renders as SVG
    expect(container.querySelector('svg')).toBeInTheDocument();
  });

  it('applies variant styles', () => {
    const { container } = render(
      <MetricCard title="Success" value="100%" variant="success" />
    );

    // Check that the card has success border styling
    const card = container.firstChild as HTMLElement;
    expect(card.className).toContain('border-success');
  });
});

describe('MetricCardCompact', () => {
  it('renders title and value', () => {
    render(<MetricCardCompact title="Items" value="50" />);

    expect(screen.getByText('Items')).toBeInTheDocument();
    expect(screen.getByText('50')).toBeInTheDocument();
  });

  it('shows trend', () => {
    render(<MetricCardCompact title="Growth" value="15%" trend={{ value: 3.5, isPositive: true }} />);

    expect(screen.getByText('+3.5%')).toBeInTheDocument();
  });
});
