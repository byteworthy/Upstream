import { useState, useEffect, useCallback } from 'react';
import { RefreshCw, Filter } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { AlertsTable } from '@/components/alerts/AlertsTable';
import { alertsApi } from '@/lib/api';
import type { Alert, AlertSeverity, AlertType } from '@/types/api';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

type StatusFilter = 'all' | 'open' | 'acknowledged' | 'resolved';

export function Alerts() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [isProcessing, setIsProcessing] = useState(false);
  const [severityFilter, setSeverityFilter] = useState<AlertSeverity | 'all'>('all');
  const [typeFilter, setTypeFilter] = useState<AlertType | 'all'>('all');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');

  const fetchAlerts = useCallback(async () => {
    try {
      setLoading(true);
      const params: Record<string, unknown> = {};
      if (severityFilter !== 'all') params.severity = severityFilter;
      if (typeFilter !== 'all') params.alert_type = typeFilter;
      if (statusFilter === 'resolved') params.is_resolved = true;
      if (statusFilter === 'acknowledged') {
        params.is_acknowledged = true;
        params.is_resolved = false;
      }
      if (statusFilter === 'open') {
        params.is_acknowledged = false;
        params.is_resolved = false;
      }

      const response = await alertsApi.list(params);
      setAlerts(response.results);
    } catch {
      // Use mock data for development
      setAlerts([
        {
          id: 1,
          title: 'High denial risk detected',
          description:
            'Claim #CLM-000123 has a 92% denial risk score due to potential coding issues',
          severity: 'critical',
          alert_type: 'denial_risk',
          specialty: 'CORE',
          claim: 123,
          claim_score: 1,
          evidence: { denial_risk_score: 92, primary_reason: 'coding_mismatch' },
          is_acknowledged: false,
          acknowledged_at: null,
          acknowledged_by: null,
          is_resolved: false,
          resolved_at: null,
          resolved_by: null,
          resolution_notes: null,
          created_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
          updated_at: new Date().toISOString(),
        },
        {
          id: 2,
          title: 'Authorization expiring',
          description: 'Patient authorization for home health services expires in 3 days',
          severity: 'high',
          alert_type: 'authorization_expiring',
          specialty: 'CORE',
          claim: null,
          claim_score: null,
          evidence: { patient_id: 'PT-456', days_until_expiry: 3 },
          is_acknowledged: true,
          acknowledged_at: new Date(Date.now() - 1 * 60 * 60 * 1000).toISOString(),
          acknowledged_by: 1,
          is_resolved: false,
          resolved_at: null,
          resolved_by: null,
          resolution_notes: null,
          created_at: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
          updated_at: new Date().toISOString(),
        },
        {
          id: 3,
          title: 'Documentation missing',
          description: 'Required face-to-face documentation not found for claim #CLM-000789',
          severity: 'medium',
          alert_type: 'documentation_missing',
          specialty: 'CORE',
          claim: 789,
          claim_score: 3,
          evidence: { missing_docs: ['f2f_encounter', 'physician_signature'] },
          is_acknowledged: false,
          acknowledged_at: null,
          acknowledged_by: null,
          is_resolved: false,
          resolved_at: null,
          resolved_by: null,
          resolution_notes: null,
          created_at: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(),
          updated_at: new Date().toISOString(),
        },
        {
          id: 4,
          title: 'Potential fraud indicator',
          description: 'Unusual billing pattern detected for provider PRV-001',
          severity: 'high',
          alert_type: 'fraud_indicator',
          specialty: 'CORE',
          claim: 456,
          claim_score: 2,
          evidence: { fraud_score: 78, pattern: 'duplicate_billing' },
          is_acknowledged: false,
          acknowledged_at: null,
          acknowledged_by: null,
          is_resolved: false,
          resolved_at: null,
          resolved_by: null,
          resolution_notes: null,
          created_at: new Date(Date.now() - 8 * 60 * 60 * 1000).toISOString(),
          updated_at: new Date().toISOString(),
        },
        {
          id: 5,
          title: 'Eligibility verification failed',
          description: 'Patient eligibility could not be verified for claim #CLM-001234',
          severity: 'medium',
          alert_type: 'eligibility_issue',
          specialty: 'CORE',
          claim: 1234,
          claim_score: 5,
          evidence: { reason: 'coverage_gap', verification_date: '2026-01-28' },
          is_acknowledged: true,
          acknowledged_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
          acknowledged_by: 1,
          is_resolved: true,
          resolved_at: new Date(Date.now() - 1 * 60 * 60 * 1000).toISOString(),
          resolved_by: 1,
          resolution_notes: 'Verified with payer - coverage confirmed',
          created_at: new Date(Date.now() - 48 * 60 * 60 * 1000).toISOString(),
          updated_at: new Date().toISOString(),
        },
        {
          id: 6,
          title: 'Coding error detected',
          description: 'ICD-10 code mismatch for procedure in claim #CLM-000567',
          severity: 'low',
          alert_type: 'coding_error',
          specialty: 'CORE',
          claim: 567,
          claim_score: 4,
          evidence: { expected_code: 'J44.1', actual_code: 'J44.0' },
          is_acknowledged: false,
          acknowledged_at: null,
          acknowledged_by: null,
          is_resolved: false,
          resolved_at: null,
          resolved_by: null,
          resolution_notes: null,
          created_at: new Date(Date.now() - 12 * 60 * 60 * 1000).toISOString(),
          updated_at: new Date().toISOString(),
        },
        {
          id: 7,
          title: 'Compliance violation warning',
          description: 'Service frequency exceeds authorized limit for patient PT-789',
          severity: 'medium',
          alert_type: 'compliance_violation',
          specialty: 'CORE',
          claim: 890,
          claim_score: 6,
          evidence: { authorized_visits: 12, actual_visits: 15 },
          is_acknowledged: false,
          acknowledged_at: null,
          acknowledged_by: null,
          is_resolved: false,
          resolved_at: null,
          resolved_by: null,
          resolution_notes: null,
          created_at: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(),
          updated_at: new Date().toISOString(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  }, [severityFilter, typeFilter, statusFilter]);

  useEffect(() => {
    fetchAlerts();
  }, [fetchAlerts]);

  const handleAcknowledge = async (id: number) => {
    try {
      setIsProcessing(true);
      await alertsApi.acknowledge(id);
      setAlerts((prev) =>
        prev.map((alert) =>
          alert.id === id
            ? { ...alert, is_acknowledged: true, acknowledged_at: new Date().toISOString() }
            : alert
        )
      );
      toast.success('Alert acknowledged');
    } catch {
      toast.error('Failed to acknowledge alert');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleResolve = async (id: number) => {
    try {
      setIsProcessing(true);
      await alertsApi.resolve(id);
      setAlerts((prev) =>
        prev.map((alert) =>
          alert.id === id
            ? {
                ...alert,
                is_resolved: true,
                resolved_at: new Date().toISOString(),
                is_acknowledged: true,
              }
            : alert
        )
      );
      toast.success('Alert resolved');
    } catch {
      toast.error('Failed to resolve alert');
    } finally {
      setIsProcessing(false);
    }
  };

  // Filter alerts based on selected filters
  const filteredAlerts = alerts.filter((alert) => {
    if (severityFilter !== 'all' && alert.severity !== severityFilter) return false;
    if (typeFilter !== 'all' && alert.alert_type !== typeFilter) return false;
    if (statusFilter === 'open' && (alert.is_acknowledged || alert.is_resolved)) return false;
    if (statusFilter === 'acknowledged' && (!alert.is_acknowledged || alert.is_resolved))
      return false;
    if (statusFilter === 'resolved' && !alert.is_resolved) return false;
    return true;
  });

  // Count by status
  const openCount = alerts.filter((a) => !a.is_acknowledged && !a.is_resolved).length;
  const acknowledgedCount = alerts.filter((a) => a.is_acknowledged && !a.is_resolved).length;
  const resolvedCount = alerts.filter((a) => a.is_resolved).length;

  if (loading && alerts.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted-foreground">Loading alerts...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Alerts</h1>
          <p className="text-muted-foreground">Monitor and respond to system alerts</p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchAlerts} disabled={loading}>
          <RefreshCw className={cn('h-4 w-4 mr-2', loading && 'animate-spin')} />
          Refresh
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 sm:grid-cols-4">
        <Card
          className={cn(
            'cursor-pointer transition-colors',
            statusFilter === 'all' && 'ring-2 ring-primary'
          )}
          onClick={() => setStatusFilter('all')}
        >
          <CardContent className="py-4">
            <div className="text-center">
              <p className="text-2xl font-bold text-foreground">{alerts.length}</p>
              <p className="text-sm text-muted-foreground">Total Alerts</p>
            </div>
          </CardContent>
        </Card>
        <Card
          className={cn(
            'cursor-pointer transition-colors',
            statusFilter === 'open' && 'ring-2 ring-primary'
          )}
          onClick={() => setStatusFilter('open')}
        >
          <CardContent className="py-4">
            <div className="text-center">
              <p className="text-2xl font-bold text-warning-500">{openCount}</p>
              <p className="text-sm text-muted-foreground">Open</p>
            </div>
          </CardContent>
        </Card>
        <Card
          className={cn(
            'cursor-pointer transition-colors',
            statusFilter === 'acknowledged' && 'ring-2 ring-primary'
          )}
          onClick={() => setStatusFilter('acknowledged')}
        >
          <CardContent className="py-4">
            <div className="text-center">
              <p className="text-2xl font-bold text-primary">{acknowledgedCount}</p>
              <p className="text-sm text-muted-foreground">Acknowledged</p>
            </div>
          </CardContent>
        </Card>
        <Card
          className={cn(
            'cursor-pointer transition-colors',
            statusFilter === 'resolved' && 'ring-2 ring-primary'
          )}
          onClick={() => setStatusFilter('resolved')}
        >
          <CardContent className="py-4">
            <div className="text-center">
              <p className="text-2xl font-bold text-success-500">{resolvedCount}</p>
              <p className="text-sm text-muted-foreground">Resolved</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Filter className="h-4 w-4" />
            Filters
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-6">
            {/* Severity Filter */}
            <div className="space-y-2">
              <label className="text-sm font-medium">Severity</label>
              <div className="flex gap-1">
                {(['all', 'critical', 'high', 'medium', 'low', 'info'] as const).map((severity) => (
                  <Button
                    key={severity}
                    variant={severityFilter === severity ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setSeverityFilter(severity)}
                    className="capitalize"
                  >
                    {severity}
                  </Button>
                ))}
              </div>
            </div>

            {/* Type Filter */}
            <div className="space-y-2">
              <label className="text-sm font-medium">Type</label>
              <div className="flex flex-wrap gap-1">
                <Button
                  variant={typeFilter === 'all' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setTypeFilter('all')}
                >
                  All
                </Button>
                {(
                  [
                    'denial_risk',
                    'fraud_indicator',
                    'compliance_violation',
                    'authorization_expiring',
                    'documentation_missing',
                    'coding_error',
                    'eligibility_issue',
                  ] as AlertType[]
                ).map((type) => (
                  <Button
                    key={type}
                    variant={typeFilter === type ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setTypeFilter(type)}
                    className="capitalize"
                  >
                    {type.replace(/_/g, ' ')}
                  </Button>
                ))}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Alerts Table */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">
            {filteredAlerts.length} Alert{filteredAlerts.length !== 1 ? 's' : ''}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <AlertsTable
            alerts={filteredAlerts}
            onAcknowledge={handleAcknowledge}
            onResolve={handleResolve}
            isProcessing={isProcessing}
          />
        </CardContent>
      </Card>
    </div>
  );
}
