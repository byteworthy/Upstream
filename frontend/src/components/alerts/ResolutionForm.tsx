import { useState } from 'react';
import { CheckCircle, XCircle, Volume2 } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface ResolutionFormProps {
  isAcknowledged: boolean;
  isResolved: boolean;
  onAcknowledge: () => void;
  onResolve: (notes: string) => void;
  onMarkAsNoise: () => void;
  isProcessing: boolean;
}

export function ResolutionForm({
  isAcknowledged,
  isResolved,
  onAcknowledge,
  onResolve,
  onMarkAsNoise,
  isProcessing,
}: ResolutionFormProps) {
  const [notes, setNotes] = useState('');
  const [showNotesInput, setShowNotesInput] = useState(false);

  const handleResolve = () => {
    onResolve(notes);
    setNotes('');
    setShowNotesInput(false);
  };

  if (isResolved) {
    return (
      <Card>
        <CardContent className="py-6">
          <div className="flex items-center justify-center gap-2 text-success-500">
            <CheckCircle className="h-5 w-5" />
            <span className="font-medium">This alert has been resolved</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Actions</CardTitle>
        <CardDescription>Take action on this alert</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Action Buttons */}
        <div className="flex flex-wrap gap-3">
          {!isAcknowledged && (
            <Button
              variant="outline"
              onClick={onAcknowledge}
              disabled={isProcessing}
              className="flex-1 min-w-[140px]"
            >
              Acknowledge
            </Button>
          )}

          {!showNotesInput ? (
            <Button
              variant="default"
              onClick={() => setShowNotesInput(true)}
              disabled={isProcessing}
              className="flex-1 min-w-[140px] bg-success-500 hover:bg-success-600"
            >
              <CheckCircle className="h-4 w-4 mr-2" />
              Resolve
            </Button>
          ) : null}

          <Button
            variant="outline"
            onClick={onMarkAsNoise}
            disabled={isProcessing}
            className="flex-1 min-w-[140px] text-muted-foreground hover:text-foreground"
          >
            <Volume2 className="h-4 w-4 mr-2" />
            Mark as Noise
          </Button>
        </div>

        {/* Resolution Notes */}
        {showNotesInput && (
          <div className="space-y-3 pt-2">
            <label htmlFor="resolution-notes" className="text-sm font-medium">
              Resolution Notes
            </label>
            <textarea
              id="resolution-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Describe how this alert was resolved..."
              className={cn(
                'flex min-h-[100px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm',
                'placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2',
                'focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50'
              )}
            />
            <div className="flex gap-2">
              <Button
                variant="default"
                onClick={handleResolve}
                disabled={isProcessing}
                className="bg-success-500 hover:bg-success-600"
              >
                <CheckCircle className="h-4 w-4 mr-2" />
                Confirm Resolution
              </Button>
              <Button
                variant="ghost"
                onClick={() => {
                  setShowNotesInput(false);
                  setNotes('');
                }}
                disabled={isProcessing}
              >
                <XCircle className="h-4 w-4 mr-2" />
                Cancel
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
