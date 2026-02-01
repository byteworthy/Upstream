import { CheckCircle, XCircle, AlertTriangle, X } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface BulkActionsProps {
  selectedCount: number;
  onAction: (action: 'approve' | 'reject' | 'escalate') => void;
  onClearSelection: () => void;
  isProcessing: boolean;
}

export function BulkActions({
  selectedCount,
  onAction,
  onClearSelection,
  isProcessing,
}: BulkActionsProps) {
  if (selectedCount === 0) {
    return null;
  }

  return (
    <div className="sticky top-0 z-10 flex items-center justify-between gap-4 rounded-lg border bg-card p-4 shadow-md">
      <div className="flex items-center gap-3">
        <span className="text-sm font-medium text-foreground">
          {selectedCount} item{selectedCount !== 1 ? 's' : ''} selected
        </span>
        <Button
          variant="ghost"
          size="sm"
          onClick={onClearSelection}
          className="text-muted-foreground"
        >
          <X className="h-4 w-4 mr-1" />
          Clear
        </Button>
      </div>

      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          className="text-success-600 hover:text-success-700 hover:bg-success-500/10"
          onClick={() => onAction('approve')}
          disabled={isProcessing}
        >
          <CheckCircle className="h-4 w-4 mr-1" />
          Approve All
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="text-danger-600 hover:text-danger-700 hover:bg-danger-500/10"
          onClick={() => onAction('reject')}
          disabled={isProcessing}
        >
          <XCircle className="h-4 w-4 mr-1" />
          Reject All
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="text-warning-600 hover:text-warning-700 hover:bg-warning-500/10"
          onClick={() => onAction('escalate')}
          disabled={isProcessing}
        >
          <AlertTriangle className="h-4 w-4 mr-1" />
          Escalate All
        </Button>
      </div>
    </div>
  );
}
