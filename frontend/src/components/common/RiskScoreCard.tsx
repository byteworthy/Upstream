import { cn } from '@/lib/utils';

interface RiskScoreCardProps {
  score: number;
  label: string;
  description?: string;
  size?: 'sm' | 'md' | 'lg';
  showTier?: boolean;
}

function getScoreColor(score: number): string {
  if (score >= 80) return 'text-success-500';
  if (score >= 60) return 'text-warning-500';
  return 'text-danger-500';
}

function getScoreGradient(score: number): string {
  if (score >= 80) return 'stroke-success-500';
  if (score >= 60) return 'stroke-warning-500';
  return 'stroke-danger-500';
}

function getScoreBg(score: number): string {
  if (score >= 80) return 'bg-success-500/10';
  if (score >= 60) return 'bg-warning-500/10';
  return 'bg-danger-500/10';
}

function getTierLabel(score: number): string {
  if (score >= 80) return 'Tier 1';
  if (score >= 60) return 'Tier 2';
  return 'Tier 3';
}

function getTierDescription(score: number): string {
  if (score >= 80) return 'Auto-process eligible';
  if (score >= 60) return 'Review required';
  return 'Manual review';
}

const sizeConfig = {
  sm: {
    wrapper: 'w-20 h-20',
    radius: 32,
    strokeWidth: 6,
    fontSize: 'text-lg',
    labelSize: 'text-xs',
  },
  md: {
    wrapper: 'w-28 h-28',
    radius: 44,
    strokeWidth: 8,
    fontSize: 'text-2xl',
    labelSize: 'text-sm',
  },
  lg: {
    wrapper: 'w-36 h-36',
    radius: 56,
    strokeWidth: 10,
    fontSize: 'text-3xl',
    labelSize: 'text-base',
  },
};

export function RiskScoreCard({
  score,
  label,
  description,
  size = 'md',
  showTier = false,
}: RiskScoreCardProps) {
  const config = sizeConfig[size];
  const circumference = 2 * Math.PI * config.radius;
  const strokeDashoffset = circumference - (score / 100) * circumference;

  return (
    <div className="flex flex-col items-center gap-2">
      {/* Circular Progress */}
      <div
        className={cn('relative flex items-center justify-center', config.wrapper)}
        title={`${label}: ${score.toFixed(1)}%`}
      >
        <svg className="w-full h-full -rotate-90" viewBox="0 0 120 120">
          {/* Background Circle */}
          <circle
            cx="60"
            cy="60"
            r={config.radius}
            className="stroke-muted"
            strokeWidth={config.strokeWidth}
            fill="none"
          />
          {/* Progress Circle */}
          <circle
            cx="60"
            cy="60"
            r={config.radius}
            className={cn('transition-all duration-500 ease-out', getScoreGradient(score))}
            strokeWidth={config.strokeWidth}
            fill="none"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
          />
        </svg>
        {/* Score Text */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={cn('font-bold', config.fontSize, getScoreColor(score))}>
            {Math.round(score)}
          </span>
          {showTier && <span className="text-xs text-muted-foreground">{getTierLabel(score)}</span>}
        </div>
      </div>

      {/* Label */}
      <div className="text-center">
        <p className={cn('font-medium text-foreground', config.labelSize)}>{label}</p>
        {description && <p className="text-xs text-muted-foreground mt-0.5">{description}</p>}
        {showTier && (
          <span
            className={cn(
              'inline-block mt-1.5 px-2 py-0.5 rounded-full text-xs font-medium',
              getScoreBg(score),
              getScoreColor(score)
            )}
          >
            {getTierDescription(score)}
          </span>
        )}
      </div>
    </div>
  );
}

// Compact inline version for tables
interface InlineRiskScoreProps {
  score: number;
  showLabel?: boolean;
}

export function InlineRiskScore({ score, showLabel = true }: InlineRiskScoreProps) {
  return (
    <div className="flex items-center gap-2">
      <div
        className={cn('flex items-center justify-center w-10 h-10 rounded-full', getScoreBg(score))}
      >
        <span className={cn('text-sm font-bold', getScoreColor(score))}>{Math.round(score)}</span>
      </div>
      {showLabel && (
        <span className={cn('text-xs font-medium', getScoreColor(score))}>
          {getTierLabel(score)}
        </span>
      )}
    </div>
  );
}
