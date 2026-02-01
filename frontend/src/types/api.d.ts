// API Types generated from OpenAPI schema for Upstream Healthcare Platform

export interface User {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  is_active: boolean;
  is_staff: boolean;
  customer?: Customer;
}

export interface Customer {
  id: number;
  name: string;
  code: string;
  is_active: boolean;
  created_at: string;
}

export interface AuthTokens {
  access: string;
  refresh: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RefreshTokenRequest {
  refresh: string;
}

// Claim types
export interface Claim {
  id: number;
  claim_id: string;
  patient_id: string;
  provider_id: string;
  payer_id: string;
  service_date: string;
  billed_amount: string;
  allowed_amount: string | null;
  paid_amount: string | null;
  claim_status: 'submitted' | 'pending' | 'approved' | 'denied' | 'appealed';
  denial_code: string | null;
  denial_reason: string | null;
  service_type: string;
  diagnosis_codes: string[];
  procedure_codes: string[];
  created_at: string;
  updated_at: string;
}

// ClaimScore types
export interface ClaimScore {
  id: number;
  claim: number;
  claim_id: string;
  overall_confidence: number;
  coding_confidence: number;
  eligibility_confidence: number;
  medical_necessity_confidence: number;
  documentation_confidence: number;
  denial_risk_score: number;
  fraud_risk_score: number;
  compliance_risk_score: number;
  automation_tier: 1 | 2 | 3;
  recommended_action:
    | 'auto_approve'
    | 'auto_submit'
    | 'queue_review'
    | 'manual_review'
    | 'escalate'
    | 'reject';
  action_reasoning: string;
  feature_importance: Record<string, number>;
  model_version: string;
  scored_at: string;
  created_at: string;
}

export interface ClaimScoreListParams {
  page?: number;
  page_size?: number;
  ordering?: string;
  automation_tier?: 1 | 2 | 3;
  min_confidence?: number;
  max_confidence?: number;
  recommended_action?: string;
  scored_after?: string;
  scored_before?: string;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

// Alert types
export type AlertSeverity = 'critical' | 'high' | 'medium' | 'low' | 'info';
export type AlertType =
  | 'denial_risk'
  | 'fraud_indicator'
  | 'compliance_violation'
  | 'authorization_expiring'
  | 'documentation_missing'
  | 'coding_error'
  | 'eligibility_issue'
  | 'system_anomaly';

export interface Alert {
  id: number;
  title: string;
  description: string;
  severity: AlertSeverity;
  alert_type: AlertType;
  claim: number | null;
  claim_score: number | null;
  evidence: Record<string, unknown>;
  is_acknowledged: boolean;
  acknowledged_at: string | null;
  acknowledged_by: number | null;
  is_resolved: boolean;
  resolved_at: string | null;
  resolved_by: number | null;
  resolution_notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface AlertListParams {
  page?: number;
  page_size?: number;
  ordering?: string;
  severity?: AlertSeverity;
  alert_type?: AlertType;
  is_acknowledged?: boolean;
  is_resolved?: boolean;
  created_after?: string;
  created_before?: string;
}

// Automation Profile types
export type AutomationStage = 'shadow' | 'assisted' | 'supervised' | 'autonomous';

export interface AutomationProfile {
  id: number;
  customer: number;
  name: string;
  automation_stage: AutomationStage;
  auto_execute_confidence: number;
  queue_review_min_confidence: number;
  queue_review_max_confidence: number;
  auto_execute_max_amount: string;
  escalate_min_amount: string;
  allowed_actions: string[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// Execution Log types
export interface ExecutionLog {
  id: number;
  claim: number;
  claim_score: number;
  action: string;
  result: 'success' | 'failure' | 'pending' | 'skipped';
  automation_profile: number;
  executed_by: number | null;
  executed_at: string;
  details: Record<string, unknown>;
  error_message: string | null;
}

// Dashboard metrics types
export interface DashboardMetrics {
  total_claims: number;
  claims_last_30_days: number;
  denial_rate: number;
  average_score: number;
  tier_distribution: {
    tier_1: number;
    tier_2: number;
    tier_3: number;
  };
  recent_alerts: Alert[];
}

// Authorization types (Home Health specialty)
export interface Authorization {
  id: number;
  patient_id: string;
  payer_id: string;
  authorization_number: string;
  service_type: string;
  start_date: string;
  end_date: string;
  authorized_units: number;
  used_units: number;
  remaining_units: number;
  status: 'active' | 'expired' | 'exhausted' | 'pending';
}
