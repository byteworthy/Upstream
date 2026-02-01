import { useNavigate } from 'react-router-dom';
import { ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { ClaimScore } from '@/types/api';
import { cn } from '@/lib/utils';

interface ClaimScoreTableProps {
  scores: ClaimScore[];
  sortBy: string;
  sortOrder: 'asc' | 'desc';
  onSort: (column: string) => void;
}

const tierColors = {
  1: 'bg-success-500/10 text-success-500',
  2: 'bg-warning-500/10 text-warning-500',
  3: 'bg-danger-500/10 text-danger-500',
};

const actionLabels: Record<string, string> = {
  auto_approve: 'Auto Approve',
  auto_submit: 'Auto Submit',
  queue_review: 'Queue Review',
  manual_review: 'Manual Review',
  escalate: 'Escalate',
  reject: 'Reject',
};

export function ClaimScoreTable({ scores, sortBy, sortOrder, onSort }: ClaimScoreTableProps) {
  const navigate = useNavigate();

  const SortIcon = ({ column }: { column: string }) => {
    if (sortBy !== column) return <ChevronsUpDown className="h-4 w-4" />;
    return sortOrder === 'asc' ? (
      <ChevronUp className="h-4 w-4" />
    ) : (
      <ChevronDown className="h-4 w-4" />
    );
  };

  const columns = [
    { key: 'claim_id', label: 'Claim ID' },
    { key: 'overall_confidence', label: 'Confidence' },
    { key: 'automation_tier', label: 'Tier' },
    { key: 'recommended_action', label: 'Recommended Action' },
    { key: 'scored_at', label: 'Scored At' },
  ];

  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full text-sm">
        <thead className="border-b border-border bg-muted/50">
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                className="px-4 py-3 text-left font-medium text-muted-foreground"
              >
                <Button
                  variant="ghost"
                  size="sm"
                  className="-ml-3 h-auto p-1 font-medium hover:bg-transparent"
                  onClick={() => onSort(column.key)}
                >
                  {column.label}
                  <SortIcon column={column.key} />
                </Button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {scores.length === 0 ? (
            <tr>
              <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">
                No claim scores found
              </td>
            </tr>
          ) : (
            scores.map((score) => (
              <tr
                key={score.id}
                onClick={() => navigate(`/claim-scores/${score.id}`)}
                className="cursor-pointer border-b border-border hover:bg-muted/50 transition-colors"
              >
                <td className="px-4 py-3 font-medium text-foreground">{score.claim_id}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="h-2 w-16 overflow-hidden rounded-full bg-muted">
                      <div
                        className={cn(
                          'h-full rounded-full',
                          score.overall_confidence >= 80
                            ? 'bg-success-500'
                            : score.overall_confidence >= 60
                              ? 'bg-warning-500'
                              : 'bg-danger-500'
                        )}
                        style={{ width: `${score.overall_confidence}%` }}
                      />
                    </div>
                    <span className="text-foreground">{score.overall_confidence.toFixed(1)}%</span>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span
                    className={cn(
                      'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium',
                      tierColors[score.automation_tier]
                    )}
                  >
                    Tier {score.automation_tier}
                  </span>
                </td>
                <td className="px-4 py-3 text-foreground">
                  {actionLabels[score.recommended_action] || score.recommended_action}
                </td>
                <td className="px-4 py-3 text-muted-foreground">
                  {new Date(score.scored_at).toLocaleDateString()}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
