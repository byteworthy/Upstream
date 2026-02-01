/**
 * Analytics provider component for React applications.
 *
 * Wraps the app and provides:
 * - Automatic page view tracking
 * - User identification
 * - Analytics context
 */

import { createContext, useContext, useEffect, type ReactNode } from 'react';
import { useLocation } from 'react-router-dom';
import { initAnalytics, identify, resetAnalytics, trackPageView } from '@/lib/analytics';

interface AnalyticsContextValue {
  identify: typeof identify;
  reset: typeof resetAnalytics;
}

const AnalyticsContext = createContext<AnalyticsContextValue | null>(null);

interface AnalyticsProviderProps {
  children: ReactNode;
  user?: {
    id: string;
    email?: string;
    role?: string;
    customerId?: string;
    plan?: string;
  };
}

export function AnalyticsProvider({ children, user }: AnalyticsProviderProps) {
  const location = useLocation();

  // Initialize analytics on mount
  useEffect(() => {
    initAnalytics(user);
  }, []);

  // Identify user when they change
  useEffect(() => {
    if (user) {
      identify(user);
    }
  }, [user?.id]);

  // Track page views on route change
  useEffect(() => {
    trackPageView({
      path: location.pathname,
      title: document.title,
      referrer: document.referrer,
    });
  }, [location.pathname]);

  const value: AnalyticsContextValue = {
    identify,
    reset: resetAnalytics,
  };

  return <AnalyticsContext.Provider value={value}>{children}</AnalyticsContext.Provider>;
}

export function useAnalyticsContext(): AnalyticsContextValue {
  const context = useContext(AnalyticsContext);
  if (!context) {
    throw new Error('useAnalyticsContext must be used within AnalyticsProvider');
  }
  return context;
}
