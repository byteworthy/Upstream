import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, ExternalLink, Clock, User, Calendar } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { SeverityBadge } from '@/components/alerts/SeverityBadge';
import { EvidenceViewer } from '@/components/alerts/EvidenceViewer';
import { ResolutionForm } from '@/components/alerts/ResolutionForm';
import { alertsApi } from '@/lib/api';
import type { Alert } from '@/types/api';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

const alertTypeLabels: Record<string, string> = {
  denial_risk: 'Denial Risk',
  fraud_indicator: 'Fraud Indicator',
  compliance_violation: 'Compliance Violation',
  authorization_expiring: 'Authorization Expiring',
  documentation_missing: 'Documentation Missing',
  coding_error: 'Coding Error',
  eligibility_issue: 'Eligibility Issue',
  system_anomaly: 'System Anomaly',
};

export function AlertDetail() {
  const { id } = useParams<{ id: string }>();
  const [alert, setAlert] = useState<Alert | null>(null);
  const [loading, setLoading] = useState(true);
  const [isProcessing, setIsProcessing] = useState(false);

  useEffect(() => {
    const fetchAlert = async () => {
      if (!id) return;
      try {
        setLoading(true);
        const data = await alertsApi.get(Number(id));
        setAlert(data);
      } catch {
        // Use mock data for development
        setAlert({
          id: Number(id),
          title: 'High denial risk detected',
          description:
            'Claim #CLM-000123 has a 92% denial risk score due to potential coding issues. The diagnosis codes do not match the procedure codes billed.',
          severity: 'critical',
          alert_type: 'denial_risk',
          specialty: 'CORE',
          claim: 123,
          claim_score: 1,
          evidence: {
            denial_risk_score: 92,
            primary_reason: 'coding_mismatch',
            diagnosis_codes: ['J44.1', 'R05.9'],
            procedure_codes: ['99213', '94640'],
            confidence: 0.89,
            model_version: '1.2.0',
            flagged_features: [
              'diagnosis_procedure_alignment',
              'historical_denial_pattern',
              'documentation_completeness',
            ],
          },
          is_acknowledged: false,
          acknowledged_at: null,
          acknowledged_by: null,
          is_resolved: false,
          resolved_at: null,
          resolved_by: null,
          resolution_notes: null,
          created_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
          updated_at: new Date().toISOString(),
        });
      } finally {
        setLoading(false);
      }
    };

    fetchAlert();
  }, [id]);

  const handleAcknowledge = async () => {
    if (!alert) return;
    try {
      setIsProcessing(true);
      await alertsApi.acknowledge(alert.id);
      setAlert({
        ...alert,
        is_acknowledged: true,
        acknowledged_at: new Date().toISOString(),
      });
      toast.success('Alert acknowledged');
    } catch {
      toast.error('Failed to acknowledge alert');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleResolve = async (notes: string) => {
    if (!alert) return;
    try {
      setIsProcessing(true);
      await alertsApi.resolve(alert.id, notes);
      setAlert({
        ...alert,
        is_acknowledged: true,
        is_resolved: true,
        resolved_at: new Date().toISOString(),
        resolution_notes: notes,
      });
      toast.success('Alert resolved');
    } catch {
      toast.error('Failed to resolve alert');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleMarkAsNoise = async () => {
    if (!alert) return;
    try {
      setIsProcessing(true);
      await alertsApi.markAsNoise(alert.id);
      setAlert({
        ...alert,
        is_acknowledged: true,
        is_resolved: true,
        resolved_at: new Date().toISOString(),
        resolution_notes: 'Marked as noise - false positive',
      });
      toast.success('Alert marked as noise');
    } catch {
      toast.error('Failed to mark alert as noise');
    } finally {
      setIsProcessing(false);
    }
  };

  const formatDateTime = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString() + ' at ' + date.toLocaleTimeString();
  };

  const getTimeSince = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffHours / 24);

    if (diffDays > 0) {
      return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;
    }
    if (diffHours > 0) {
      return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
    }
    const diffMinutes = Math.floor(diffMs / (1000 * 60));
    return `${diffMinutes} minute${diffMinutes !== 1 ? 's' : ''} ago`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted-foreground">Loading alert details...</div>
      </div>
    );
  }

  if (!alert) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted-foreground">Alert not found</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link to="/alerts">
            <ArrowLeft className="h-5 w-5" />
          </Link>
        </Button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-foreground">{alert.title}</h1>
          <p className="text-muted-foreground">Alert ID: {alert.id}</p>
        </div>
      </div>

      {/* Alert Summary */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Severity</CardTitle>
          </CardHeader>
          <CardContent>
            <SeverityBadge severity={alert.severity} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Type</CardTitle>
          </CardHeader>
          <CardContent>
            <span className="text-lg font-semibold text-foreground">
              {alertTypeLabels[alert.alert_type] || alert.alert_type}
            </span>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Created</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-muted-foreground" />
              <span className="text-foreground">{getTimeSince(alert.created_at)}</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Status</CardTitle>
          </CardHeader>
          <CardContent>
            <span
              className={cn(
                'inline-flex items-center rounded-md border px-3 py-1 text-sm font-medium',
                alert.is_resolved
                  ? 'bg-success-500/10 text-success-500 border-success-500/20'
                  : alert.is_acknowledged
                    ? 'bg-primary/10 text-primary border-primary/20'
                    : 'bg-warning-500/10 text-warning-500 border-warning-500/20'
              )}
            >
              {alert.is_resolved ? 'Resolved' : alert.is_acknowledged ? 'Acknowledged' : 'Open'}
            </span>
          </CardContent>
        </Card>
      </div>

      {/* Description */}
      <Card>
        <CardHeader>
          <CardTitle>Description</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-foreground">{alert.description}</p>
        </CardContent>
      </Card>

      {/* Related Claim */}
      {alert.claim && (
        <Card>
          <CardHeader>
            <CardTitle>Related Claim</CardTitle>
            <CardDescription>This alert is associated with a specific claim</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-4">
              <span className="text-lg font-medium text-foreground">Claim #{alert.claim}</span>
              <Button variant="outline" size="sm" asChild>
                <Link to={`/claim-scores/${alert.claim_score}`}>
                  <ExternalLink className="h-4 w-4 mr-2" />
                  View Claim Score
                </Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Evidence */}
      <EvidenceViewer evidence={alert.evidence} />

      {/* Resolution Form */}
      <ResolutionForm
        isAcknowledged={alert.is_acknowledged}
        isResolved={alert.is_resolved}
        onAcknowledge={handleAcknowledge}
        onResolve={handleResolve}
        onMarkAsNoise={handleMarkAsNoise}
        isProcessing={isProcessing}
      />

      {/* Activity Timeline */}
      <Card>
        <CardHeader>
          <CardTitle>Activity Timeline</CardTitle>
          <CardDescription>History of actions taken on this alert</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {/* Created */}
            <div className="flex items-start gap-4">
              <div className="mt-1 flex h-8 w-8 items-center justify-center rounded-full bg-muted">
                <Calendar className="h-4 w-4 text-muted-foreground" />
              </div>
              <div>
                <p className="font-medium text-foreground">Alert Created</p>
                <p className="text-sm text-muted-foreground">{formatDateTime(alert.created_at)}</p>
              </div>
            </div>

            {/* Acknowledged */}
            {alert.is_acknowledged && alert.acknowledged_at && (
              <div className="flex items-start gap-4">
                <div className="mt-1 flex h-8 w-8 items-center justify-center rounded-full bg-primary/10">
                  <User className="h-4 w-4 text-primary" />
                </div>
                <div>
                  <p className="font-medium text-foreground">Acknowledged</p>
                  <p className="text-sm text-muted-foreground">
                    {formatDateTime(alert.acknowledged_at)}
                    {alert.acknowledged_by && ` by User #${alert.acknowledged_by}`}
                  </p>
                </div>
              </div>
            )}

            {/* Resolved */}
            {alert.is_resolved && alert.resolved_at && (
              <div className="flex items-start gap-4">
                <div className="mt-1 flex h-8 w-8 items-center justify-center rounded-full bg-success-500/10">
                  <User className="h-4 w-4 text-success-500" />
                </div>
                <div>
                  <p className="font-medium text-foreground">Resolved</p>
                  <p className="text-sm text-muted-foreground">
                    {formatDateTime(alert.resolved_at)}
                    {alert.resolved_by && ` by User #${alert.resolved_by}`}
                  </p>
                  {alert.resolution_notes && (
                    <p className="mt-1 text-sm text-foreground bg-muted rounded p-2">
                      {alert.resolution_notes}
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
