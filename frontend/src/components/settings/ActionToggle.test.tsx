import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ActionToggle } from './ActionToggle';

describe('ActionToggle', () => {
  it('renders label', () => {
    render(<ActionToggle label="Auto-Approve Claims" checked={false} onChange={() => {}} />);

    expect(screen.getByText('Auto-Approve Claims')).toBeInTheDocument();
  });

  it('renders description when provided', () => {
    render(
      <ActionToggle
        label="Test Action"
        description="This action does something"
        checked={false}
        onChange={() => {}}
      />
    );

    expect(screen.getByText('This action does something')).toBeInTheDocument();
  });

  it('shows checked state', () => {
    render(<ActionToggle label="Test" checked={true} onChange={() => {}} />);

    const toggle = screen.getByRole('switch');
    expect(toggle).toHaveAttribute('aria-checked', 'true');
  });

  it('shows unchecked state', () => {
    render(<ActionToggle label="Test" checked={false} onChange={() => {}} />);

    const toggle = screen.getByRole('switch');
    expect(toggle).toHaveAttribute('aria-checked', 'false');
  });

  it('calls onChange when clicked', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<ActionToggle label="Test" checked={false} onChange={onChange} />);

    const toggle = screen.getByRole('switch');
    await user.click(toggle);

    expect(onChange).toHaveBeenCalledWith(true);
  });

  it('calls onChange with false when checked and clicked', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<ActionToggle label="Test" checked={true} onChange={onChange} />);

    const toggle = screen.getByRole('switch');
    await user.click(toggle);

    expect(onChange).toHaveBeenCalledWith(false);
  });

  it('does not call onChange when disabled', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<ActionToggle label="Test" checked={false} disabled onChange={onChange} />);

    const toggle = screen.getByRole('switch');
    await user.click(toggle);

    expect(onChange).not.toHaveBeenCalled();
  });

  it('is disabled when disabled prop is true', () => {
    render(<ActionToggle label="Test" checked={false} disabled onChange={() => {}} />);

    const toggle = screen.getByRole('switch');
    expect(toggle).toBeDisabled();
  });
});
