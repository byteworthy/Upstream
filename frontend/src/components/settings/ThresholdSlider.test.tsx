import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ThresholdSlider } from './ThresholdSlider';

describe('ThresholdSlider', () => {
  it('renders label and value', () => {
    render(<ThresholdSlider label="Confidence Threshold" value={80} onChange={() => {}} />);

    expect(screen.getByText('Confidence Threshold')).toBeInTheDocument();
    expect(screen.getByText('80%')).toBeInTheDocument();
  });

  it('renders description when provided', () => {
    render(
      <ThresholdSlider
        label="Test"
        value={50}
        description="This is a description"
        onChange={() => {}}
      />
    );

    expect(screen.getByText('This is a description')).toBeInTheDocument();
  });

  it('formats dollar values correctly', () => {
    render(<ThresholdSlider label="Amount" value={5000} unit="$" onChange={() => {}} />);

    expect(screen.getByText('$5,000')).toBeInTheDocument();
  });

  it('calls onChange when slider is moved', () => {
    const onChange = vi.fn();
    render(<ThresholdSlider label="Test" value={50} onChange={onChange} />);

    const slider = screen.getByRole('slider');
    fireEvent.change(slider, { target: { value: '75' } });

    expect(onChange).toHaveBeenCalledWith(75);
  });

  it('respects min and max values', () => {
    render(<ThresholdSlider label="Test" value={50} min={10} max={90} onChange={() => {}} />);

    const slider = screen.getByRole('slider');
    expect(slider).toHaveAttribute('min', '10');
    expect(slider).toHaveAttribute('max', '90');
  });

  it('shows ticks when showTicks is true', () => {
    render(
      <ThresholdSlider label="Test" value={50} min={0} max={100} showTicks onChange={() => {}} />
    );

    expect(screen.getByText('0%')).toBeInTheDocument();
    // 50% appears both in value display and ticks, so use getAllByText
    expect(screen.getAllByText('50%').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('100%')).toBeInTheDocument();
  });

  it('is disabled when disabled prop is true', () => {
    render(<ThresholdSlider label="Test" value={50} disabled onChange={() => {}} />);

    const slider = screen.getByRole('slider');
    expect(slider).toBeDisabled();
  });
});
