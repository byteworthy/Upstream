import { Navigate, useLocation } from 'react-router-dom';
import { useCustomer, type SpecialtyType } from '@/contexts/CustomerContext';

interface SpecialtyRouteProps {
  specialty: SpecialtyType;
  children: React.ReactNode;
  fallbackPath?: string;
}

/**
 * Route guard that only renders children if the customer has the specified specialty enabled.
 * Redirects to fallback path (default: dashboard) if specialty is not enabled.
 */
export function SpecialtyRoute({
  specialty,
  children,
  fallbackPath = '/dashboard',
}: SpecialtyRouteProps) {
  const { customer, loading, hasSpecialty } = useCustomer();
  const location = useLocation();

  // Show loading state while customer data is being fetched
  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    );
  }

  // If no customer data, redirect to login (handled by AppLayout, but be safe)
  if (!customer) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Check if customer has the required specialty
  if (!hasSpecialty(specialty)) {
    return <Navigate to={fallbackPath} replace />;
  }

  return <>{children}</>;
}

/**
 * Higher-order component version of SpecialtyRoute for use with route definitions.
 */
export function withSpecialtyGuard(
  Component: React.ComponentType,
  specialty: SpecialtyType,
  fallbackPath?: string
) {
  return function SpecialtyGuardedComponent() {
    return (
      <SpecialtyRoute specialty={specialty} fallbackPath={fallbackPath}>
        <Component />
      </SpecialtyRoute>
    );
  };
}
