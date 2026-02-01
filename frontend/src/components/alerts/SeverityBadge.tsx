import { cn } from '@/lib/utils';
import type { AlertSeverity } from '@/types/api';

interface SeverityBadgeProps {
  severity: AlertSeverity;
  size?: 'sm' | 'md';
}

const severityConfig: Record<AlertSeverity, { label: string; className: string }> = {
  critical: {
    label: 'Critical',
    className: 'bg-danger-500/10 text-danger-500 border-danger-500/20',
  },
  high: {
    label: 'High',
    className: 'bg-danger-500/10 text-danger-600 border-danger-500/20',
  },
  medium: {
    label: 'Medium',
    className: 'bg-warning-500/10 text-warning-600 border-warning-500/20',
  },
  low: {
    label: 'Low',
    className: 'bg-muted text-muted-foreground border-muted-foreground/20',
  },
  info: {
    label: 'Info',
    className: 'bg-primary/10 text-primary border-primary/20',
  },
};

export function SeverityBadge({ severity, size = 'md' }: SeverityBadgeProps) {
  const config = severityConfig[severity];

  return (
    <span
      className={cn(
        'inline-flex items-center rounded-md border font-medium',
        size === 'sm' ? 'px-1.5 py-0.5 text-xs' : 'px-2 py-1 text-xs',
        config.className
      )}
    >
      {config.label}
    </span>
  );
}
