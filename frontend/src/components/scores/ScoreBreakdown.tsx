import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';

interface ScoreBreakdownProps {
  coding: number;
  eligibility: number;
  necessity: number;
  documentation: number;
  denialRisk: number;
  fraudRisk: number;
  complianceRisk: number;
}

interface ScoreBarProps {
  label: string;
  value: number;
  isRisk?: boolean;
}

function ScoreBar({ label, value, isRisk = false }: ScoreBarProps) {
  const percentage = Math.min(100, Math.max(0, value));
  const colorClass = isRisk
    ? value > 50
      ? 'bg-danger-500'
      : value > 25
        ? 'bg-warning-500'
        : 'bg-success-500'
    : value >= 80
      ? 'bg-success-500'
      : value >= 60
        ? 'bg-warning-500'
        : 'bg-danger-500';

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-sm">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-medium text-foreground">{value.toFixed(1)}%</span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={cn('h-full rounded-full transition-all', colorClass)}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}

export function ScoreBreakdown({
  coding,
  eligibility,
  necessity,
  documentation,
  denialRisk,
  fraudRisk,
  complianceRisk,
}: ScoreBreakdownProps) {
  return (
    <div className="grid gap-6 md:grid-cols-2">
      {/* Confidence Scores */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Confidence Scores</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <ScoreBar label="Coding Confidence" value={coding} />
          <ScoreBar label="Eligibility Confidence" value={eligibility} />
          <ScoreBar label="Medical Necessity" value={necessity} />
          <ScoreBar label="Documentation Confidence" value={documentation} />
        </CardContent>
      </Card>

      {/* Risk Scores */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Risk Scores</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <ScoreBar label="Denial Risk" value={denialRisk} isRisk />
          <ScoreBar label="Fraud Risk" value={fraudRisk} isRisk />
          <ScoreBar label="Compliance Risk" value={complianceRisk} isRisk />
        </CardContent>
      </Card>
    </div>
  );
}
