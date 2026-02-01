import { Link } from 'react-router-dom';
import { AlertTriangle, AlertCircle, Info, ChevronRight } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import type { Alert, AlertSeverity } from '@/types/api';
import { cn } from '@/lib/utils';

interface RecentAlertsProps {
  alerts: Alert[];
}

const severityConfig: Record<AlertSeverity, { icon: typeof AlertTriangle; className: string }> = {
  critical: { icon: AlertTriangle, className: 'text-danger-500' },
  high: { icon: AlertTriangle, className: 'text-danger-500' },
  medium: { icon: AlertCircle, className: 'text-warning-500' },
  low: { icon: Info, className: 'text-upstream-500' },
  info: { icon: Info, className: 'text-muted-foreground' },
};

export function RecentAlerts({ alerts }: RecentAlertsProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle>Recent Alerts</CardTitle>
          <CardDescription>Latest 5 unresolved alerts</CardDescription>
        </div>
        <Button variant="ghost" size="sm" asChild>
          <Link to="/alerts" className="flex items-center gap-1">
            View all
            <ChevronRight className="h-4 w-4" />
          </Link>
        </Button>
      </CardHeader>
      <CardContent>
        {alerts.length === 0 ? (
          <p className="text-center text-sm text-muted-foreground py-4">No recent alerts</p>
        ) : (
          <div className="space-y-4">
            {alerts.map((alert) => {
              const config = severityConfig[alert.severity];
              const Icon = config.icon;
              return (
                <Link
                  key={alert.id}
                  to={`/alerts/${alert.id}`}
                  className="flex items-start gap-3 rounded-lg p-2 hover:bg-accent transition-colors"
                >
                  <Icon className={cn('h-5 w-5 mt-0.5', config.className)} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-foreground truncate">{alert.title}</p>
                    <p className="text-xs text-muted-foreground truncate">{alert.description}</p>
                    <p className="text-xs text-muted-foreground mt-1">
                      {new Date(alert.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <span
                    className={cn(
                      'text-xs font-medium px-2 py-0.5 rounded-full',
                      alert.severity === 'critical' && 'bg-danger-500/10 text-danger-500',
                      alert.severity === 'high' && 'bg-danger-500/10 text-danger-500',
                      alert.severity === 'medium' && 'bg-warning-500/10 text-warning-500',
                      alert.severity === 'low' && 'bg-upstream-500/10 text-upstream-500',
                      alert.severity === 'info' && 'bg-muted text-muted-foreground'
                    )}
                  >
                    {alert.severity}
                  </span>
                </Link>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
