import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Clock, CheckCircle, XCircle, AlertTriangle, ExternalLink } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { cn } from '@/lib/utils';
import type { WorkQueueItem } from '@/types/api';

interface QueueItemProps {
  item: WorkQueueItem;
  isSelected: boolean;
  onSelect: (id: number, selected: boolean) => void;
  onAction: (id: number, action: 'approve' | 'reject' | 'escalate') => void;
}

export function QueueItem({ item, isSelected, onSelect, onAction }: QueueItemProps) {
  const [isProcessing, setIsProcessing] = useState(false);

  const handleAction = async (action: 'approve' | 'reject' | 'escalate') => {
    setIsProcessing(true);
    await onAction(item.id, action);
    setIsProcessing(false);
  };

  // Calculate time in queue
  const getTimeInQueue = (createdAt: string) => {
    const created = new Date(createdAt);
    const now = new Date();
    const diffMs = now.getTime() - created.getTime();
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffHours / 24);

    if (diffDays > 0) {
      return `${diffDays}d ${diffHours % 24}h`;
    }
    if (diffHours > 0) {
      return `${diffHours}h`;
    }
    const diffMinutes = Math.floor(diffMs / (1000 * 60));
    return `${diffMinutes}m`;
  };

  // SLA indicator color based on time in queue
  const getSlaColor = (createdAt: string) => {
    const created = new Date(createdAt);
    const now = new Date();
    const diffHours = (now.getTime() - created.getTime()) / (1000 * 60 * 60);

    if (diffHours < 4) return 'text-success-500';
    if (diffHours < 24) return 'text-warning-500';
    return 'text-danger-500';
  };

  const priorityColors = {
    high: 'border-l-danger-500',
    medium: 'border-l-warning-500',
    low: 'border-l-muted-foreground',
  };

  return (
    <Card
      className={cn(
        'border-l-4 transition-colors',
        priorityColors[item.priority],
        isSelected && 'bg-muted/50'
      )}
    >
      <CardContent className="p-4">
        <div className="flex items-start gap-4">
          {/* Checkbox */}
          <div className="pt-1">
            <Checkbox
              checked={isSelected}
              onCheckedChange={(checked) => onSelect(item.id, checked as boolean)}
              aria-label={`Select ${item.claim_id}`}
            />
          </div>

          {/* Main Content */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 mb-2">
              <Link
                to={`/claim-scores/${item.claim_score_id}`}
                className="text-lg font-semibold text-foreground hover:text-primary hover:underline"
              >
                {item.claim_id}
              </Link>
              <span
                className={cn(
                  'inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium',
                  item.priority === 'high'
                    ? 'bg-danger-500/10 text-danger-500 border-danger-500/20'
                    : item.priority === 'medium'
                      ? 'bg-warning-500/10 text-warning-500 border-warning-500/20'
                      : 'bg-muted text-muted-foreground border-muted-foreground/20'
                )}
              >
                {item.priority.charAt(0).toUpperCase() + item.priority.slice(1)} Priority
              </span>
            </div>

            <p className="text-sm text-muted-foreground mb-2 line-clamp-2">{item.reason}</p>

            <div className="flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
              <div className="flex items-center gap-1.5">
                <span className="font-medium">Confidence:</span>
                <span
                  className={cn(
                    'font-semibold',
                    item.confidence >= 80
                      ? 'text-success-500'
                      : item.confidence >= 60
                        ? 'text-warning-500'
                        : 'text-danger-500'
                  )}
                >
                  {item.confidence.toFixed(1)}%
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="font-medium">Amount:</span>
                <span className="text-foreground">
                  ${item.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                </span>
              </div>
              <div className={cn('flex items-center gap-1.5', getSlaColor(item.created_at))}>
                <Clock className="h-4 w-4" />
                <span>{getTimeInQueue(item.created_at)} in queue</span>
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="icon" asChild title="View details">
              <Link to={`/claim-scores/${item.claim_score_id}`}>
                <ExternalLink className="h-4 w-4" />
              </Link>
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="text-success-600 hover:text-success-700 hover:bg-success-500/10"
              onClick={() => handleAction('approve')}
              disabled={isProcessing}
              title="Approve claim"
            >
              <CheckCircle className="h-4 w-4 mr-1" />
              Approve
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="text-danger-600 hover:text-danger-700 hover:bg-danger-500/10"
              onClick={() => handleAction('reject')}
              disabled={isProcessing}
              title="Reject claim"
            >
              <XCircle className="h-4 w-4 mr-1" />
              Reject
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="text-warning-600 hover:text-warning-700 hover:bg-warning-500/10"
              onClick={() => handleAction('escalate')}
              disabled={isProcessing}
              title="Escalate to senior reviewer"
            >
              <AlertTriangle className="h-4 w-4 mr-1" />
              Escalate
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
