import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RiskScoreCard, InlineRiskScore } from './RiskScoreCard';

describe('RiskScoreCard', () => {
  it('renders score value', () => {
    render(<RiskScoreCard score={85} label="Confidence Score" />);

    expect(screen.getByText('85')).toBeInTheDocument();
    expect(screen.getByText('Confidence Score')).toBeInTheDocument();
  });

  it('renders description when provided', () => {
    render(<RiskScoreCard score={75} label="Risk Score" description="Based on historical data" />);

    expect(screen.getByText('Based on historical data')).toBeInTheDocument();
  });

  it('shows tier when showTier is true', () => {
    render(<RiskScoreCard score={95} label="Score" showTier />);

    expect(screen.getByText('Tier 1')).toBeInTheDocument();
  });

  it('applies correct tier for high scores', () => {
    render(<RiskScoreCard score={92} label="Score" showTier />);
    expect(screen.getByText('Tier 1')).toBeInTheDocument();
  });

  it('applies correct tier for medium scores', () => {
    render(<RiskScoreCard score={75} label="Score" showTier />);
    expect(screen.getByText('Tier 2')).toBeInTheDocument();
  });

  it('applies correct tier for low scores', () => {
    render(<RiskScoreCard score={50} label="Score" showTier />);
    expect(screen.getByText('Tier 3')).toBeInTheDocument();
  });

  it('renders with different sizes', () => {
    const { rerender } = render(<RiskScoreCard score={80} label="Score" size="sm" />);
    expect(screen.getByText('80')).toBeInTheDocument();

    rerender(<RiskScoreCard score={80} label="Score" size="lg" />);
    expect(screen.getByText('80')).toBeInTheDocument();
  });
});

describe('InlineRiskScore', () => {
  it('renders score with tier label by default', () => {
    render(<InlineRiskScore score={85} />);

    expect(screen.getByText('85')).toBeInTheDocument();
    expect(screen.getByText('Tier 1')).toBeInTheDocument();
  });

  it('hides tier label when showLabel is false', () => {
    render(<InlineRiskScore score={85} showLabel={false} />);

    expect(screen.getByText('85')).toBeInTheDocument();
    expect(screen.queryByText('Tier 1')).not.toBeInTheDocument();
  });

  it('renders different score values', () => {
    const { rerender } = render(<InlineRiskScore score={0} />);
    expect(screen.getByText('0')).toBeInTheDocument();

    rerender(<InlineRiskScore score={100} />);
    expect(screen.getByText('100')).toBeInTheDocument();

    rerender(<InlineRiskScore score={50} />);
    expect(screen.getByText('50')).toBeInTheDocument();
  });
});
