import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MetricCard } from './MetricCard';

describe('MetricCard', () => {
  it('renders title and value', () => {
    render(<MetricCard title="Total Claims" value="1,234" />);

    expect(screen.getByText('Total Claims')).toBeInTheDocument();
    expect(screen.getByText('1,234')).toBeInTheDocument();
  });

  it('renders with icon', () => {
    const TestIcon = () => <svg data-testid="test-icon" />;
    render(<MetricCard title="Test Metric" value="100" icon={<TestIcon />} />);

    expect(screen.getByTestId('test-icon')).toBeInTheDocument();
  });

  it('shows positive trend correctly', () => {
    render(
      <MetricCard title="Revenue" value="$50,000" trend={{ value: 12.5, isPositive: true }} />
    );

    expect(screen.getByText('+12.5%')).toBeInTheDocument();
  });

  it('shows negative trend correctly', () => {
    render(<MetricCard title="Errors" value="25" trend={{ value: 5.2, isPositive: false }} />);

    expect(screen.getByText('-5.2%')).toBeInTheDocument();
  });

  it('renders description when provided', () => {
    render(<MetricCard title="Active Users" value="500" description="Last 30 days" />);

    expect(screen.getByText('Last 30 days')).toBeInTheDocument();
  });
});
