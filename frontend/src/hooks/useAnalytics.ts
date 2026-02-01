/**
 * React hooks for analytics tracking.
 */

import { useEffect, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import {
  trackPageView,
  trackEvent,
  SignupEvents,
  OnboardingEvents,
  ClaimEvents,
  BillingEvents,
  FeatureEvents,
} from '@/lib/analytics';

/**
 * Hook to track page views automatically on route changes.
 */
export function usePageTracking(): void {
  const location = useLocation();

  useEffect(() => {
    trackPageView({
      path: location.pathname,
      title: document.title,
      referrer: document.referrer,
    });
  }, [location.pathname]);
}

/**
 * Hook to track a feature being used.
 */
export function useFeatureTracking(featureName: string): {
  trackUsage: () => void;
  trackError: (errorType: string) => void;
} {
  const trackUsage = useCallback(() => {
    FeatureEvents.used(featureName);
  }, [featureName]);

  const trackError = useCallback(
    (errorType: string) => {
      FeatureEvents.error(featureName, errorType);
    },
    [featureName]
  );

  return { trackUsage, trackError };
}

/**
 * Hook for signup flow tracking.
 */
export function useSignupTracking() {
  return {
    trackStarted: SignupEvents.started,
    trackTierSelected: SignupEvents.tierSelected,
    trackAccountCreated: SignupEvents.accountCreated,
    trackPaymentEntered: SignupEvents.paymentEntered,
    trackCompleted: SignupEvents.completed,
    trackAbandoned: SignupEvents.abandoned,
  };
}

/**
 * Hook for onboarding flow tracking.
 */
export function useOnboardingTracking() {
  return {
    trackStarted: OnboardingEvents.started,
    trackStepCompleted: OnboardingEvents.stepCompleted,
    trackOrganizationConfigured: OnboardingEvents.organizationConfigured,
    trackIntegrationSelected: OnboardingEvents.integrationSelected,
    trackTeamInvited: OnboardingEvents.teamInvited,
    trackCompleted: OnboardingEvents.completed,
    trackSkipped: OnboardingEvents.skipped,
  };
}

/**
 * Hook for claim-related tracking.
 */
export function useClaimTracking() {
  return {
    trackViewed: ClaimEvents.viewed,
    trackScored: ClaimEvents.scored,
    trackActionTaken: ClaimEvents.actionTaken,
    trackExported: ClaimEvents.exported,
  };
}

/**
 * Hook for billing tracking.
 */
export function useBillingTracking() {
  return {
    trackPlanViewed: BillingEvents.planViewed,
    trackPlanChanged: BillingEvents.planChanged,
    trackInvoiceDownloaded: BillingEvents.invoiceDownloaded,
    trackPaymentMethodUpdated: BillingEvents.paymentMethodUpdated,
  };
}

/**
 * Hook for custom event tracking.
 */
export function useEventTracking() {
  const track = useCallback((name: string, properties?: Record<string, unknown>) => {
    trackEvent({ name, properties });
  }, []);

  return { track };
}
