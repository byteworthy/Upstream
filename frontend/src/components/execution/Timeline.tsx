import { LogEntry, type ExecutionLogEntry } from './LogEntry';

interface TimelineProps {
  entries: ExecutionLogEntry[];
  loading?: boolean;
}

export function Timeline({ entries, loading }: TimelineProps) {
  if (loading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="flex gap-4 animate-pulse">
            <div className="flex flex-col items-center">
              <div className="h-10 w-10 rounded-full bg-muted" />
              <div className="h-20 w-0.5 bg-muted" />
            </div>
            <div className="flex-1">
              <div className="h-24 rounded-lg bg-muted" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (entries.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <div className="rounded-full bg-muted p-4">
          <svg
            className="h-8 w-8 text-muted-foreground"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        </div>
        <h3 className="mt-4 text-lg font-medium text-foreground">No execution logs</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          Execution logs will appear here when actions are taken.
        </p>
      </div>
    );
  }

  return (
    <div className="relative">
      {entries.map((entry, index) => (
        <LogEntry key={entry.id} entry={entry} isLast={index === entries.length - 1} />
      ))}
    </div>
  );
}

export type { ExecutionLogEntry };
