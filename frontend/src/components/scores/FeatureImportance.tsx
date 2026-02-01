import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';

interface FeatureImportanceProps {
  features: Record<string, number>;
}

export function FeatureImportance({ features }: FeatureImportanceProps) {
  // Sort features by importance descending
  const sortedFeatures = Object.entries(features)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 10); // Top 10 features

  const maxValue = sortedFeatures.length > 0 ? sortedFeatures[0][1] : 1;

  const formatFeatureName = (name: string): string => {
    return name
      .replace(/_/g, ' ')
      .replace(/([A-Z])/g, ' $1')
      .replace(/^./, (str) => str.toUpperCase())
      .trim();
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Feature Importance</CardTitle>
        <CardDescription>Top contributing factors to the score</CardDescription>
      </CardHeader>
      <CardContent>
        {sortedFeatures.length === 0 ? (
          <p className="text-center text-sm text-muted-foreground py-4">
            No feature importance data available
          </p>
        ) : (
          <div className="space-y-3">
            {sortedFeatures.map(([feature, value], index) => {
              const percentage = (value / maxValue) * 100;
              const colorIntensity = Math.floor((1 - index / sortedFeatures.length) * 100);

              return (
                <div key={feature} className="space-y-1">
                  <div className="flex justify-between text-sm">
                    <span className="text-foreground">{formatFeatureName(feature)}</span>
                    <span className="font-medium text-muted-foreground">
                      {(value * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className="h-4 w-full overflow-hidden rounded bg-muted">
                    <div
                      className={cn(
                        'h-full rounded transition-all',
                        index === 0
                          ? 'bg-upstream-600'
                          : index < 3
                            ? 'bg-upstream-500'
                            : 'bg-upstream-400'
                      )}
                      style={{
                        width: `${percentage}%`,
                        opacity: `${Math.max(40, colorIntensity)}%`,
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
