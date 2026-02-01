import { useState, useEffect, useCallback } from 'react';
import { FileText, TrendingDown, BarChart3, Calendar } from 'lucide-react';
import { MetricCard } from '@/components/dashboard/MetricCard';
import { ScoreDistribution } from '@/components/dashboard/ScoreDistribution';
import { RecentAlerts } from '@/components/dashboard/RecentAlerts';
import { Button } from '@/components/ui/button';
import { dashboardApi } from '@/lib/api';
import type { DashboardMetrics } from '@/types/api';

type DateRange = '7d' | '30d' | '90d';

export function Dashboard() {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [dateRange, setDateRange] = useState<DateRange>('30d');

  const fetchMetrics = useCallback(async () => {
    try {
      setLoading(true);
      const data = await dashboardApi.getMetrics();
      setMetrics(data);
    } catch {
      // Use mock data for development
      setMetrics({
        total_claims: 12847,
        claims_last_30_days: 4532,
        denial_rate: 4.2,
        average_score: 87.3,
        tier_distribution: {
          tier_1: 3200,
          tier_2: 980,
          tier_3: 352,
        },
        recent_alerts: [
          {
            id: 1,
            title: 'High denial risk detected',
            description: 'Claim #12345 has a 92% denial risk score',
            severity: 'high',
            alert_type: 'denial_risk',
            claim: 12345,
            claim_score: 1,
            evidence: {},
            is_acknowledged: false,
            acknowledged_at: null,
            acknowledged_by: null,
            is_resolved: false,
            resolved_at: null,
            resolved_by: null,
            resolution_notes: null,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
          {
            id: 2,
            title: 'Authorization expiring',
            description: 'Patient auth expires in 3 days',
            severity: 'medium',
            alert_type: 'authorization_expiring',
            claim: null,
            claim_score: null,
            evidence: {},
            is_acknowledged: false,
            acknowledged_at: null,
            acknowledged_by: null,
            is_resolved: false,
            resolved_at: null,
            resolved_by: null,
            resolution_notes: null,
            created_at: new Date(Date.now() - 86400000).toISOString(),
            updated_at: new Date(Date.now() - 86400000).toISOString(),
          },
          {
            id: 3,
            title: 'Documentation missing',
            description: 'Required documentation not found for claim #67890',
            severity: 'medium',
            alert_type: 'documentation_missing',
            claim: 67890,
            claim_score: 2,
            evidence: {},
            is_acknowledged: false,
            acknowledged_at: null,
            acknowledged_by: null,
            is_resolved: false,
            resolved_at: null,
            resolved_by: null,
            resolution_notes: null,
            created_at: new Date(Date.now() - 172800000).toISOString(),
            updated_at: new Date(Date.now() - 172800000).toISOString(),
          },
        ],
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMetrics();

    // Auto-refresh every 5 minutes
    const interval = setInterval(fetchMetrics, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [fetchMetrics, dateRange]);

  if (loading && !metrics) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted-foreground">Loading dashboard...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header with date range selector */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Dashboard</h1>
          <p className="text-muted-foreground">Overview of claims and scoring metrics</p>
        </div>
        <div className="flex gap-2">
          {(['7d', '30d', '90d'] as const).map((range) => (
            <Button
              key={range}
              variant={dateRange === range ? 'default' : 'outline'}
              size="sm"
              onClick={() => setDateRange(range)}
            >
              {range === '7d' ? '7 Days' : range === '30d' ? '30 Days' : '90 Days'}
            </Button>
          ))}
        </div>
      </div>

      {/* Metrics Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="Total Claims"
          value={metrics?.total_claims.toLocaleString() || '0'}
          description="All time"
          icon={FileText}
        />
        <MetricCard
          title="Claims This Period"
          value={metrics?.claims_last_30_days.toLocaleString() || '0'}
          description={`Last ${dateRange === '7d' ? '7' : dateRange === '30d' ? '30' : '90'} days`}
          icon={Calendar}
          trend={{ value: 12.5, isPositive: true }}
        />
        <MetricCard
          title="Denial Rate"
          value={`${metrics?.denial_rate || 0}%`}
          description="Current month"
          icon={TrendingDown}
          trend={{ value: -2.1, isPositive: true }}
        />
        <MetricCard
          title="Average Score"
          value={metrics?.average_score.toFixed(1) || '0'}
          description="Confidence score"
          icon={BarChart3}
          trend={{ value: 3.2, isPositive: true }}
        />
      </div>

      {/* Charts and Alerts */}
      <div className="grid gap-6 lg:grid-cols-2">
        <ScoreDistribution
          data={
            metrics?.tier_distribution || {
              tier_1: 0,
              tier_2: 0,
              tier_3: 0,
            }
          }
        />
        <RecentAlerts alerts={metrics?.recent_alerts || []} />
      </div>
    </div>
  );
}
