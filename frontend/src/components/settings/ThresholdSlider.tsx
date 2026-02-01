import { cn } from '@/lib/utils';

interface ThresholdSliderProps {
  label: string;
  description?: string;
  value: number;
  min?: number;
  max?: number;
  step?: number;
  unit?: string;
  onChange: (value: number) => void;
  showValue?: boolean;
  showTicks?: boolean;
  disabled?: boolean;
}

export function ThresholdSlider({
  label,
  description,
  value,
  min = 0,
  max = 100,
  step = 1,
  unit = '%',
  onChange,
  showValue = true,
  showTicks = false,
  disabled = false,
}: ThresholdSliderProps) {
  const percentage = ((value - min) / (max - min)) * 100;

  const getColorClass = () => {
    if (percentage >= 80) return 'bg-success-500';
    if (percentage >= 60) return 'bg-warning-500';
    return 'bg-danger-500';
  };

  const formatValue = (val: number) => {
    if (unit === '$') {
      return `$${val.toLocaleString()}`;
    }
    return `${val}${unit}`;
  };

  return (
    <div className={cn('space-y-2', disabled && 'opacity-50')}>
      <div className="flex items-center justify-between">
        <div>
          <label className="text-sm font-medium text-foreground">{label}</label>
          {description && <p className="text-xs text-muted-foreground">{description}</p>}
        </div>
        {showValue && (
          <span className="text-sm font-semibold text-foreground">{formatValue(value)}</span>
        )}
      </div>

      <div className="relative">
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          disabled={disabled}
          className={cn(
            'w-full h-2 rounded-full appearance-none cursor-pointer',
            'bg-muted',
            '[&::-webkit-slider-thumb]:appearance-none',
            '[&::-webkit-slider-thumb]:h-5',
            '[&::-webkit-slider-thumb]:w-5',
            '[&::-webkit-slider-thumb]:rounded-full',
            '[&::-webkit-slider-thumb]:bg-foreground',
            '[&::-webkit-slider-thumb]:border-2',
            '[&::-webkit-slider-thumb]:border-background',
            '[&::-webkit-slider-thumb]:shadow-md',
            '[&::-webkit-slider-thumb]:cursor-pointer',
            '[&::-webkit-slider-thumb]:transition-transform',
            '[&::-webkit-slider-thumb]:hover:scale-110',
            '[&::-moz-range-thumb]:h-5',
            '[&::-moz-range-thumb]:w-5',
            '[&::-moz-range-thumb]:rounded-full',
            '[&::-moz-range-thumb]:bg-foreground',
            '[&::-moz-range-thumb]:border-2',
            '[&::-moz-range-thumb]:border-background',
            '[&::-moz-range-thumb]:cursor-pointer',
            disabled && 'cursor-not-allowed'
          )}
          style={{
            background: `linear-gradient(to right, var(--color-primary) 0%, var(--color-primary) ${percentage}%, hsl(var(--muted)) ${percentage}%, hsl(var(--muted)) 100%)`,
          }}
        />

        {/* Progress bar overlay */}
        <div
          className={cn(
            'absolute top-0 left-0 h-2 rounded-full pointer-events-none',
            getColorClass()
          )}
          style={{ width: `${percentage}%` }}
        />
      </div>

      {showTicks && (
        <div className="flex justify-between text-xs text-muted-foreground px-1">
          <span>{formatValue(min)}</span>
          <span>{formatValue((min + max) / 2)}</span>
          <span>{formatValue(max)}</span>
        </div>
      )}
    </div>
  );
}
