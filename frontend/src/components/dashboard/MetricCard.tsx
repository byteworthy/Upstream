import { type LucideIcon, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { cn } from '@/lib/utils';

interface MetricCardProps {
  title: string;
  value: string | number;
  description?: string;
  icon?: LucideIcon;
  trend?: {
    value: number;
    isPositive: boolean;
  };
  /** Optional sparkline data points (0-100 normalized) */
  sparkline?: number[];
  /** Visual variant */
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'primary';
  className?: string;
}

// Mini sparkline component
function Sparkline({ data, color = 'currentColor' }: { data: number[]; color?: string }) {
  if (data.length < 2) return null;

  const width = 80;
  const height = 32;
  const padding = 2;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const points = data
    .map((value, index) => {
      const x = padding + (index / (data.length - 1)) * (width - padding * 2);
      const y = height - padding - ((value - min) / range) * (height - padding * 2);
      return `${x},${y}`;
    })
    .join(' ');

  // Create gradient fill
  const fillPoints = `${padding},${height - padding} ${points} ${width - padding},${height - padding}`;

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className="overflow-visible"
      aria-hidden="true"
    >
      {/* Gradient fill under line */}
      <defs>
        <linearGradient id={`sparkline-gradient-${color}`} x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor={color} stopOpacity="0.2" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon
        points={fillPoints}
        fill={`url(#sparkline-gradient-${color})`}
      />
      {/* Line */}
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="drop-shadow-sm"
      />
      {/* End dot */}
      <circle
        cx={width - padding}
        cy={height - padding - ((data[data.length - 1] - min) / range) * (height - padding * 2)}
        r="2.5"
        fill={color}
        className="drop-shadow-sm"
      />
    </svg>
  );
}

const variantStyles = {
  default: {
    border: 'border-border',
    iconBg: 'bg-muted',
    iconColor: 'text-muted-foreground',
    sparklineColor: 'var(--color-muted-foreground)',
  },
  primary: {
    border: 'border-primary/20',
    iconBg: 'bg-primary/10',
    iconColor: 'text-primary',
    sparklineColor: 'var(--color-primary)',
  },
  success: {
    border: 'border-success-500/20',
    iconBg: 'bg-success-500/10',
    iconColor: 'text-success-500',
    sparklineColor: 'var(--color-success-500)',
  },
  warning: {
    border: 'border-warning-500/20',
    iconBg: 'bg-warning-500/10',
    iconColor: 'text-warning-500',
    sparklineColor: 'var(--color-warning-500)',
  },
  danger: {
    border: 'border-danger-500/20',
    iconBg: 'bg-danger-500/10',
    iconColor: 'text-danger-500',
    sparklineColor: 'var(--color-danger-500)',
  },
};

export function MetricCard({
  title,
  value,
  description,
  icon: Icon,
  trend,
  sparkline,
  variant = 'default',
  className,
}: MetricCardProps) {
  const styles = variantStyles[variant];

  const TrendIcon = trend
    ? trend.value > 0
      ? TrendingUp
      : trend.value < 0
        ? TrendingDown
        : Minus
    : null;

  return (
    <div
      className={cn(
        'group relative overflow-hidden rounded-xl border bg-card p-5',
        'transition-all duration-300 ease-out',
        'hover:shadow-lg hover:shadow-primary/5 hover:-translate-y-0.5',
        styles.border,
        className
      )}
    >
      {/* Subtle gradient overlay on hover */}
      <div className="absolute inset-0 bg-gradient-to-br from-primary/[0.02] to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />

      <div className="relative flex items-start justify-between">
        {/* Content */}
        <div className="flex-1 min-w-0">
          {/* Header */}
          <div className="flex items-center gap-2 mb-3">
            {Icon && (
              <div className={cn('rounded-lg p-2', styles.iconBg)}>
                <Icon className={cn('h-4 w-4', styles.iconColor)} />
              </div>
            )}
            <span className="text-sm font-medium text-muted-foreground truncate">{title}</span>
          </div>

          {/* Value */}
          <div className="metric-display metric-large text-foreground mb-1" data-numeric>
            {value}
          </div>

          {/* Trend and description */}
          {(trend || description) && (
            <div className="flex items-center gap-2 text-sm">
              {trend && (
                <span
                  className={cn(
                    'inline-flex items-center gap-1 font-medium tabular-nums',
                    trend.isPositive ? 'text-success-500' : 'text-danger-500'
                  )}
                >
                  {TrendIcon && <TrendIcon className="h-3.5 w-3.5" />}
                  {trend.isPositive && trend.value > 0 && '+'}
                  {trend.value}%
                </span>
              )}
              {description && (
                <span className="text-muted-foreground truncate">{description}</span>
              )}
            </div>
          )}
        </div>

        {/* Sparkline */}
        {sparkline && sparkline.length > 1 && (
          <div className="flex-shrink-0 ml-4 opacity-70 group-hover:opacity-100 transition-opacity">
            <Sparkline data={sparkline} color={styles.sparklineColor} />
          </div>
        )}
      </div>
    </div>
  );
}

// Compact metric for dense layouts
export function MetricCardCompact({
  title,
  value,
  trend,
  className,
}: Pick<MetricCardProps, 'title' | 'value' | 'trend' | 'className'>) {
  return (
    <div
      className={cn(
        'flex items-center justify-between rounded-lg border border-border bg-card px-4 py-3',
        'transition-colors duration-200 hover:bg-muted/50',
        className
      )}
    >
      <span className="text-sm text-muted-foreground">{title}</span>
      <div className="flex items-center gap-2">
        <span className="font-mono font-semibold text-foreground tabular-nums">{value}</span>
        {trend && (
          <span
            className={cn(
              'text-xs font-medium tabular-nums',
              trend.isPositive ? 'text-success-500' : 'text-danger-500'
            )}
          >
            {trend.isPositive && trend.value > 0 && '+'}
            {trend.value}%
          </span>
        )}
      </div>
    </div>
  );
}
