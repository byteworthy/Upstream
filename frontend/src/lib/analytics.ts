/**
 * Analytics tracking module for Upstream Healthcare.
 *
 * Supports multiple analytics providers:
 * - Segment (primary)
 * - Google Analytics 4
 * - Custom backend events
 *
 * HIPAA Compliance:
 * - Never track PHI in analytics events
 * - User IDs are hashed before sending
 * - PII fields are automatically stripped
 */

// Types
interface AnalyticsUser {
  id: string;
  email?: string;
  role?: string;
  customerId?: string;
  plan?: string;
}

interface AnalyticsEvent {
  name: string;
  properties?: Record<string, unknown>;
  timestamp?: Date;
}

interface PageViewEvent {
  path: string;
  title?: string;
  referrer?: string;
}

// Configuration
const ANALYTICS_CONFIG = {
  enabled: import.meta.env.VITE_ANALYTICS_ENABLED === 'true',
  segmentWriteKey: import.meta.env.VITE_SEGMENT_WRITE_KEY || '',
  gaTrackingId: import.meta.env.VITE_GA_TRACKING_ID || '',
  debug: import.meta.env.DEV,
};

// PII fields to automatically strip from event properties
const PII_FIELDS = [
  'ssn',
  'socialSecurityNumber',
  'dateOfBirth',
  'dob',
  'patientName',
  'patientId',
  'mrn',
  'medicalRecordNumber',
  'diagnosis',
  'medication',
  'address',
  'phoneNumber',
  'phone',
  'insuranceId',
  'memberId',
];

/**
 * Strip PII fields from an object recursively.
 */
function stripPii(obj: Record<string, unknown>): Record<string, unknown> {
  const result: Record<string, unknown> = {};

  for (const [key, value] of Object.entries(obj)) {
    const lowerKey = key.toLowerCase();

    // Skip PII fields
    if (PII_FIELDS.some((field) => lowerKey.includes(field.toLowerCase()))) {
      continue;
    }

    // Recursively process nested objects
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      result[key] = stripPii(value as Record<string, unknown>);
    } else {
      result[key] = value;
    }
  }

  return result;
}

/**
 * Hash a string using SHA-256 for user identification.
 */
async function hashString(str: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(str);
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
}

/**
 * Log analytics events in debug mode.
 */
function debugLog(type: string, data: unknown): void {
  if (ANALYTICS_CONFIG.debug) {
    console.log(`[Analytics] ${type}:`, data);
  }
}

// Current user state
let currentUser: AnalyticsUser | null = null;

/**
 * Initialize analytics with user context.
 */
export async function initAnalytics(user?: AnalyticsUser): Promise<void> {
  if (!ANALYTICS_CONFIG.enabled) {
    debugLog('Init', 'Analytics disabled');
    return;
  }

  if (user) {
    currentUser = user;
    await identify(user);
  }

  debugLog('Init', { config: ANALYTICS_CONFIG, user });
}

/**
 * Identify the current user for analytics.
 */
export async function identify(user: AnalyticsUser): Promise<void> {
  if (!ANALYTICS_CONFIG.enabled) return;

  currentUser = user;

  // Hash user ID for privacy
  const hashedId = await hashString(user.id);

  const traits = {
    role: user.role,
    plan: user.plan,
    customerId: user.customerId ? await hashString(user.customerId) : undefined,
  };

  // Segment
  if (window.analytics?.identify) {
    window.analytics.identify(hashedId, traits);
  }

  // Google Analytics
  if (window.gtag) {
    window.gtag('config', ANALYTICS_CONFIG.gaTrackingId, {
      user_id: hashedId,
    });
  }

  debugLog('Identify', { hashedId, traits });
}

/**
 * Track a page view.
 */
export function trackPageView(event: PageViewEvent): void {
  if (!ANALYTICS_CONFIG.enabled) return;

  // Segment
  if (window.analytics?.page) {
    window.analytics.page(event.title, {
      path: event.path,
      referrer: event.referrer,
    });
  }

  // Google Analytics
  if (window.gtag) {
    window.gtag('event', 'page_view', {
      page_path: event.path,
      page_title: event.title,
    });
  }

  debugLog('Page View', event);
}

/**
 * Track a custom event.
 */
export function trackEvent(event: AnalyticsEvent): void {
  if (!ANALYTICS_CONFIG.enabled) return;

  // Strip PII from properties
  const safeProperties = event.properties ? stripPii(event.properties) : {};

  // Add common context
  const properties = {
    ...safeProperties,
    timestamp: event.timestamp || new Date(),
    userRole: currentUser?.role,
    userPlan: currentUser?.plan,
  };

  // Segment
  if (window.analytics?.track) {
    window.analytics.track(event.name, properties);
  }

  // Google Analytics
  if (window.gtag) {
    window.gtag('event', event.name, properties);
  }

  debugLog('Event', { name: event.name, properties });
}

/**
 * Reset analytics state (on logout).
 */
export function resetAnalytics(): void {
  currentUser = null;

  if (window.analytics?.reset) {
    window.analytics.reset();
  }

  debugLog('Reset', 'Analytics state cleared');
}

// Pre-defined event helpers

/**
 * Track signup flow events.
 */
export const SignupEvents = {
  started: () => trackEvent({ name: 'signup_started' }),
  tierSelected: (tier: string) =>
    trackEvent({
      name: 'signup_tier_selected',
      properties: { tier },
    }),
  accountCreated: () => trackEvent({ name: 'signup_account_created' }),
  paymentEntered: () => trackEvent({ name: 'signup_payment_entered' }),
  completed: (tier: string) =>
    trackEvent({
      name: 'signup_completed',
      properties: { tier },
    }),
  abandoned: (step: string) =>
    trackEvent({
      name: 'signup_abandoned',
      properties: { step },
    }),
};

/**
 * Track onboarding flow events.
 */
export const OnboardingEvents = {
  started: () => trackEvent({ name: 'onboarding_started' }),
  stepCompleted: (step: string) =>
    trackEvent({
      name: 'onboarding_step_completed',
      properties: { step },
    }),
  organizationConfigured: (type: string) =>
    trackEvent({
      name: 'onboarding_organization_configured',
      properties: { organizationType: type },
    }),
  integrationSelected: (integration: string) =>
    trackEvent({
      name: 'onboarding_integration_selected',
      properties: { integration },
    }),
  teamInvited: (count: number) =>
    trackEvent({
      name: 'onboarding_team_invited',
      properties: { inviteCount: count },
    }),
  completed: () => trackEvent({ name: 'onboarding_completed' }),
  skipped: (step: string) =>
    trackEvent({
      name: 'onboarding_step_skipped',
      properties: { step },
    }),
};

/**
 * Track claim-related events.
 */
export const ClaimEvents = {
  viewed: (claimId: string) =>
    trackEvent({
      name: 'claim_viewed',
      properties: { claimIdHash: claimId.slice(0, 8) }, // Only first 8 chars
    }),
  scored: (score: number, riskLevel: string) =>
    trackEvent({
      name: 'claim_scored',
      properties: { score, riskLevel },
    }),
  actionTaken: (action: string) =>
    trackEvent({
      name: 'claim_action_taken',
      properties: { action },
    }),
  exported: (format: string, count: number) =>
    trackEvent({
      name: 'claims_exported',
      properties: { format, count },
    }),
};

/**
 * Track billing events.
 */
export const BillingEvents = {
  planViewed: () => trackEvent({ name: 'billing_plan_viewed' }),
  planChanged: (fromPlan: string, toPlan: string) =>
    trackEvent({
      name: 'billing_plan_changed',
      properties: { fromPlan, toPlan },
    }),
  invoiceDownloaded: () => trackEvent({ name: 'billing_invoice_downloaded' }),
  paymentMethodUpdated: () => trackEvent({ name: 'billing_payment_updated' }),
};

/**
 * Track feature usage events.
 */
export const FeatureEvents = {
  used: (featureName: string) =>
    trackEvent({
      name: 'feature_used',
      properties: { feature: featureName },
    }),
  error: (featureName: string, errorType: string) =>
    trackEvent({
      name: 'feature_error',
      properties: { feature: featureName, errorType },
    }),
};

// Type declarations for window globals
declare global {
  interface Window {
    analytics?: {
      identify: (userId: string, traits?: Record<string, unknown>) => void;
      track: (event: string, properties?: Record<string, unknown>) => void;
      page: (name?: string, properties?: Record<string, unknown>) => void;
      reset: () => void;
    };
    gtag?: (...args: unknown[]) => void;
  }
}
