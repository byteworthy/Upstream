import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, ExternalLink } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { ScoreBreakdown } from '@/components/scores/ScoreBreakdown';
import { FeatureImportance } from '@/components/scores/FeatureImportance';
import { claimScoresApi } from '@/lib/api';
import type { ClaimScore } from '@/types/api';
import { cn } from '@/lib/utils';

const tierColors = {
  1: 'bg-success-500/10 text-success-500 border-success-500/20',
  2: 'bg-warning-500/10 text-warning-500 border-warning-500/20',
  3: 'bg-danger-500/10 text-danger-500 border-danger-500/20',
};

const actionLabels: Record<string, { label: string; description: string }> = {
  auto_approve: { label: 'Auto Approve', description: 'Claim can be automatically approved' },
  auto_submit: { label: 'Auto Submit', description: 'Claim can be automatically submitted' },
  queue_review: { label: 'Queue for Review', description: 'Claim requires human review' },
  manual_review: { label: 'Manual Review', description: 'Claim requires detailed manual review' },
  escalate: { label: 'Escalate', description: 'Claim should be escalated to senior reviewer' },
  reject: { label: 'Reject', description: 'Claim should be rejected' },
};

export function ClaimScoreDetail() {
  const { id } = useParams<{ id: string }>();
  const [score, setScore] = useState<ClaimScore | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchScore = async () => {
      if (!id) return;
      try {
        setLoading(true);
        const data = await claimScoresApi.get(Number(id));
        setScore(data);
      } catch {
        // Use mock data for development
        setScore({
          id: Number(id),
          claim: 1234,
          claim_id: `CLM-${id?.padStart(6, '0')}`,
          overall_confidence: 78.5,
          coding_confidence: 85.2,
          eligibility_confidence: 92.1,
          medical_necessity_confidence: 68.4,
          documentation_confidence: 72.3,
          denial_risk_score: 15.6,
          fraud_risk_score: 3.2,
          compliance_risk_score: 8.9,
          automation_tier: 2,
          recommended_action: 'queue_review',
          action_reasoning:
            'The claim has high eligibility confidence but lower documentation confidence. A brief review of the supporting documentation is recommended before processing.',
          feature_importance: {
            diagnosis_match: 0.25,
            procedure_validity: 0.22,
            provider_history: 0.18,
            documentation_completeness: 0.15,
            authorization_status: 0.1,
            patient_eligibility: 0.05,
            service_date_validity: 0.03,
            billing_code_accuracy: 0.02,
          },
          model_version: '1.2.0',
          scored_at: new Date().toISOString(),
          created_at: new Date().toISOString(),
        });
      } finally {
        setLoading(false);
      }
    };

    fetchScore();
  }, [id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted-foreground">Loading score details...</div>
      </div>
    );
  }

  if (!score) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted-foreground">Score not found</div>
      </div>
    );
  }

  const action = actionLabels[score.recommended_action] || {
    label: score.recommended_action,
    description: '',
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link to="/claim-scores">
            <ArrowLeft className="h-5 w-5" />
          </Link>
        </Button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-foreground">Claim Score Details</h1>
          <p className="text-muted-foreground">Score ID: {score.id}</p>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Claim ID</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <span className="text-xl font-bold text-foreground">{score.claim_id}</span>
              <Button variant="ghost" size="icon" asChild>
                <a href={`/claims/${score.claim}`} title="View claim">
                  <ExternalLink className="h-4 w-4" />
                </a>
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Overall Confidence
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <span className="text-xl font-bold text-foreground">
                {score.overall_confidence.toFixed(1)}%
              </span>
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
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
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Automation Tier
            </CardTitle>
          </CardHeader>
          <CardContent>
            <span
              className={cn(
                'inline-flex items-center rounded-md border px-3 py-1 text-lg font-semibold',
                tierColors[score.automation_tier]
              )}
            >
              Tier {score.automation_tier}
            </span>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Scored At</CardTitle>
          </CardHeader>
          <CardContent>
            <span className="text-xl font-bold text-foreground">
              {new Date(score.scored_at).toLocaleDateString()}
            </span>
            <p className="text-sm text-muted-foreground">
              {new Date(score.scored_at).toLocaleTimeString()}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Recommended Action */}
      <Card>
        <CardHeader>
          <CardTitle>Recommended Action</CardTitle>
          <CardDescription>{action.description}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-start gap-4">
            <div
              className={cn(
                'rounded-lg px-4 py-2 text-lg font-semibold',
                score.recommended_action === 'auto_approve' ||
                  score.recommended_action === 'auto_submit'
                  ? 'bg-success-500/10 text-success-500'
                  : score.recommended_action === 'reject'
                    ? 'bg-danger-500/10 text-danger-500'
                    : 'bg-warning-500/10 text-warning-500'
              )}
            >
              {action.label}
            </div>
            <div className="flex-1">
              <p className="text-sm font-medium text-foreground">Reasoning</p>
              <p className="mt-1 text-sm text-muted-foreground">{score.action_reasoning}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Score Breakdown */}
      <ScoreBreakdown
        coding={score.coding_confidence}
        eligibility={score.eligibility_confidence}
        necessity={score.medical_necessity_confidence}
        documentation={score.documentation_confidence}
        denialRisk={score.denial_risk_score}
        fraudRisk={score.fraud_risk_score}
        complianceRisk={score.compliance_risk_score}
      />

      {/* Feature Importance */}
      <FeatureImportance features={score.feature_importance} />

      {/* Model Info */}
      <Card>
        <CardContent className="py-4">
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>Model Version: {score.model_version}</span>
            <span>Score Created: {new Date(score.created_at).toLocaleString()}</span>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
