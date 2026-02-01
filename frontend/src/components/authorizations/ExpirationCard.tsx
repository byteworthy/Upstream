import { Link } from 'react-router-dom';
import { Calendar, User, FileText } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import type { Authorization } from '@/types/api';
import { cn } from '@/lib/utils';

interface ExpirationCardProps {
  authorization: Authorization;
}

export function ExpirationCard({ authorization }: ExpirationCardProps) {
  const daysUntilExpiry = Math.ceil(
    (new Date(authorization.end_date).getTime() - Date.now()) / (1000 * 60 * 60 * 24)
  );

  const getExpiryColor = () => {
    if (daysUntilExpiry <= 0) return 'bg-danger-500/10 border-danger-500/20';
    if (daysUntilExpiry <= 7) return 'bg-danger-500/10 border-danger-500/20';
    if (daysUntilExpiry <= 14) return 'bg-warning-500/10 border-warning-500/20';
    if (daysUntilExpiry <= 30) return 'bg-warning-500/10 border-warning-500/20';
    return 'bg-success-500/10 border-success-500/20';
  };

  const getExpiryText = () => {
    if (daysUntilExpiry <= 0) return 'Expired';
    if (daysUntilExpiry === 1) return '1 day left';
    return `${daysUntilExpiry} days left`;
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  const usagePercentage = (authorization.used_units / authorization.authorized_units) * 100;

  return (
    <Card className={cn('border', getExpiryColor())}>
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2">
              <span className="font-medium text-foreground truncate">
                {authorization.authorization_number}
              </span>
              <span
                className={cn(
                  'inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium',
                  authorization.status === 'active'
                    ? 'bg-success-500/10 text-success-500'
                    : authorization.status === 'expired'
                      ? 'bg-danger-500/10 text-danger-500'
                      : authorization.status === 'exhausted'
                        ? 'bg-warning-500/10 text-warning-500'
                        : 'bg-muted text-muted-foreground'
                )}
              >
                {authorization.status.charAt(0).toUpperCase() + authorization.status.slice(1)}
              </span>
            </div>

            <div className="space-y-1 text-sm text-muted-foreground">
              <div className="flex items-center gap-2">
                <User className="h-3.5 w-3.5" />
                <span>Patient: {authorization.patient_id}</span>
              </div>
              <div className="flex items-center gap-2">
                <FileText className="h-3.5 w-3.5" />
                <span>{authorization.service_type}</span>
              </div>
              <div className="flex items-center gap-2">
                <Calendar className="h-3.5 w-3.5" />
                <span>
                  {formatDate(authorization.start_date)} - {formatDate(authorization.end_date)}
                </span>
              </div>
            </div>

            {/* Usage Progress */}
            <div className="mt-3">
              <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
                <span>
                  {authorization.used_units} / {authorization.authorized_units} units used
                </span>
                <span>{usagePercentage.toFixed(0)}%</span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                <div
                  className={cn(
                    'h-full rounded-full transition-all',
                    usagePercentage >= 90
                      ? 'bg-danger-500'
                      : usagePercentage >= 75
                        ? 'bg-warning-500'
                        : 'bg-success-500'
                  )}
                  style={{ width: `${Math.min(usagePercentage, 100)}%` }}
                />
              </div>
            </div>
          </div>

          <div className="text-right">
            <span
              className={cn(
                'text-sm font-medium',
                daysUntilExpiry <= 0
                  ? 'text-danger-500'
                  : daysUntilExpiry <= 7
                    ? 'text-danger-500'
                    : daysUntilExpiry <= 14
                      ? 'text-warning-500'
                      : 'text-muted-foreground'
              )}
            >
              {getExpiryText()}
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
