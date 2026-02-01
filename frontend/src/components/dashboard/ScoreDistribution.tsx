import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

interface TierData {
  tier_1: number;
  tier_2: number;
  tier_3: number;
}

interface ScoreDistributionProps {
  data: TierData;
}

export function ScoreDistribution({ data }: ScoreDistributionProps) {
  const total = data.tier_1 + data.tier_2 + data.tier_3;

  const tiers = [
    {
      name: 'Tier 1',
      description: 'Auto-execute',
      value: data.tier_1,
      percentage: total > 0 ? ((data.tier_1 / total) * 100).toFixed(1) : '0',
      color: 'bg-success-500',
    },
    {
      name: 'Tier 2',
      description: 'Queue Review',
      value: data.tier_2,
      percentage: total > 0 ? ((data.tier_2 / total) * 100).toFixed(1) : '0',
      color: 'bg-warning-500',
    },
    {
      name: 'Tier 3',
      description: 'Manual Review',
      value: data.tier_3,
      percentage: total > 0 ? ((data.tier_3 / total) * 100).toFixed(1) : '0',
      color: 'bg-danger-500',
    },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Score Distribution</CardTitle>
        <CardDescription>Claims by automation tier</CardDescription>
      </CardHeader>
      <CardContent>
        {/* Pie Chart Visualization */}
        <div className="mb-6 flex items-center justify-center">
          <div className="relative h-40 w-40">
            <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90">
              {total > 0 && (
                <>
                  {/* Tier 1 */}
                  <circle
                    cx="50"
                    cy="50"
                    r="40"
                    fill="transparent"
                    stroke="currentColor"
                    strokeWidth="20"
                    strokeDasharray={`${(data.tier_1 / total) * 251.2} 251.2`}
                    className="text-success-500"
                  />
                  {/* Tier 2 */}
                  <circle
                    cx="50"
                    cy="50"
                    r="40"
                    fill="transparent"
                    stroke="currentColor"
                    strokeWidth="20"
                    strokeDasharray={`${(data.tier_2 / total) * 251.2} 251.2`}
                    strokeDashoffset={`${-(data.tier_1 / total) * 251.2}`}
                    className="text-warning-500"
                  />
                  {/* Tier 3 */}
                  <circle
                    cx="50"
                    cy="50"
                    r="40"
                    fill="transparent"
                    stroke="currentColor"
                    strokeWidth="20"
                    strokeDasharray={`${(data.tier_3 / total) * 251.2} 251.2`}
                    strokeDashoffset={`${-((data.tier_1 + data.tier_2) / total) * 251.2}`}
                    className="text-danger-500"
                  />
                </>
              )}
            </svg>
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center">
                <p className="text-2xl font-bold text-foreground">{total.toLocaleString()}</p>
                <p className="text-xs text-muted-foreground">Total</p>
              </div>
            </div>
          </div>
        </div>

        {/* Legend */}
        <div className="space-y-3">
          {tiers.map((tier) => (
            <div key={tier.name} className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className={`h-3 w-3 rounded-full ${tier.color}`} />
                <div>
                  <p className="text-sm font-medium text-foreground">{tier.name}</p>
                  <p className="text-xs text-muted-foreground">{tier.description}</p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-sm font-medium text-foreground">{tier.value.toLocaleString()}</p>
                <p className="text-xs text-muted-foreground">{tier.percentage}%</p>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
