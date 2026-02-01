import { useState } from 'react';
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Clock,
  ChevronDown,
  ChevronUp,
  User,
  FileText,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';

export interface ExecutionLogEntry {
  id: number;
  action: string;
  action_type: 'auto_execute' | 'queue_review' | 'escalate' | 'manual_override' | 'system';
  result: 'success' | 'failure' | 'pending' | 'skipped';
  claim_id?: number;
  claim_score_id?: number;
  user_id?: number | null;
  user_name?: string | null;
  details?: Record<string, unknown>;
  error_message?: string | null;
  execution_time_ms?: number;
  created_at: string;
}

interface LogEntryProps {
  entry: ExecutionLogEntry;
  isLast: boolean;
}

const actionTypeColors: Record<string, string> = {
  auto_execute: 'bg-success-500/10 text-success-500 border-success-500/20',
  queue_review: 'bg-warning-500/10 text-warning-500 border-warning-500/20',
  escalate: 'bg-danger-500/10 text-danger-500 border-danger-500/20',
  manual_override: 'bg-primary/10 text-primary border-primary/20',
  system: 'bg-muted text-muted-foreground border-muted',
};

const actionTypeLabels: Record<string, string> = {
  auto_execute: 'Auto Execute',
  queue_review: 'Queue Review',
  escalate: 'Escalate',
  manual_override: 'Manual Override',
  system: 'System',
};

const resultIcons: Record<string, React.ReactNode> = {
  success: <CheckCircle2 className="h-5 w-5 text-success-500" />,
  failure: <XCircle className="h-5 w-5 text-danger-500" />,
  pending: <Clock className="h-5 w-5 text-warning-500" />,
  skipped: <AlertTriangle className="h-5 w-5 text-muted-foreground" />,
};

const resultLabels: Record<string, string> = {
  success: 'Success',
  failure: 'Failed',
  pending: 'Pending',
  skipped: 'Skipped',
};

export function LogEntry({ entry, isLast }: LogEntryProps) {
  const [expanded, setExpanded] = useState(false);

  const formatTimestamp = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleString();
  };

  const formatExecutionTime = (ms: number | undefined) => {
    if (!ms) return null;
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  return (
    <div className="relative flex gap-4">
      {/* Timeline connector */}
      <div className="flex flex-col items-center">
        <div
          className={cn(
            'flex h-10 w-10 items-center justify-center rounded-full border-2',
            entry.result === 'success' && 'border-success-500 bg-success-500/10',
            entry.result === 'failure' && 'border-danger-500 bg-danger-500/10',
            entry.result === 'pending' && 'border-warning-500 bg-warning-500/10',
            entry.result === 'skipped' && 'border-muted bg-muted'
          )}
        >
          {resultIcons[entry.result]}
        </div>
        {!isLast && <div className="h-full w-0.5 bg-border" />}
      </div>

      {/* Entry content */}
      <div className="flex-1 pb-6">
        <Card>
          <CardContent className="p-4">
            {/* Header */}
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <h3 className="font-semibold text-foreground">{entry.action}</h3>
                  <span
                    className={cn(
                      'inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium',
                      actionTypeColors[entry.action_type]
                    )}
                  >
                    {actionTypeLabels[entry.action_type] || entry.action_type}
                  </span>
                  <span
                    className={cn(
                      'inline-flex items-center gap-1 text-xs',
                      entry.result === 'success' && 'text-success-500',
                      entry.result === 'failure' && 'text-danger-500',
                      entry.result === 'pending' && 'text-warning-500',
                      entry.result === 'skipped' && 'text-muted-foreground'
                    )}
                  >
                    {resultLabels[entry.result]}
                  </span>
                </div>

                {/* Meta info */}
                <div className="mt-1 flex items-center gap-4 text-sm text-muted-foreground flex-wrap">
                  <span className="flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {formatTimestamp(entry.created_at)}
                  </span>
                  {entry.user_name && (
                    <span className="flex items-center gap-1">
                      <User className="h-3 w-3" />
                      {entry.user_name}
                    </span>
                  )}
                  {entry.claim_id && (
                    <span className="flex items-center gap-1">
                      <FileText className="h-3 w-3" />
                      Claim #{entry.claim_id}
                    </span>
                  )}
                  {entry.execution_time_ms && (
                    <span className="text-xs">
                      ({formatExecutionTime(entry.execution_time_ms)})
                    </span>
                  )}
                </div>

                {/* Error message */}
                {entry.error_message && (
                  <div className="mt-2 rounded bg-danger-500/10 p-2 text-sm text-danger-500">
                    {entry.error_message}
                  </div>
                )}
              </div>

              {/* Expand button */}
              {entry.details && Object.keys(entry.details).length > 0 && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setExpanded(!expanded)}
                  className="shrink-0"
                >
                  {expanded ? (
                    <ChevronUp className="h-4 w-4" />
                  ) : (
                    <ChevronDown className="h-4 w-4" />
                  )}
                </Button>
              )}
            </div>

            {/* Expanded details */}
            {expanded && entry.details && (
              <div className="mt-4 rounded bg-muted p-3">
                <p className="mb-2 text-xs font-medium text-muted-foreground">Details</p>
                <pre className="overflow-x-auto text-xs text-foreground">
                  {JSON.stringify(entry.details, null, 2)}
                </pre>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
