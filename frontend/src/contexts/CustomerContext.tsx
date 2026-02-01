/**
 * Customer context provider for managing customer profile and specialty modules.
 *
 * Provides:
 * - Current customer profile with specialty information
 * - Methods to enable/disable specialty modules
 * - Optimistic UI updates with rollback on error
 * - Loading and error states
 */

import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import { toast } from 'sonner';

// Types
export type SpecialtyType = 'DIALYSIS' | 'ABA' | 'PTOT' | 'IMAGING' | 'HOME_HEALTH';

export interface SpecialtyModule {
  id: number;
  specialty: SpecialtyType;
  enabled: boolean;
  enabled_at: string;
  is_primary: boolean;
}

export interface CustomerProfile {
  id: number;
  name: string;
  specialty_type: SpecialtyType | null;
  specialty_modules: SpecialtyModule[];
  enabled_specialties: SpecialtyType[];
}

export interface CustomerContextValue {
  customer: CustomerProfile | null;
  loading: boolean;
  error: string | null;
  /** Check if customer has a specific specialty enabled */
  hasSpecialty: (specialty: SpecialtyType | string) => boolean;
  /** Enable a specialty module (with optimistic update) */
  enableSpecialty: (specialty: SpecialtyType) => Promise<void>;
  /** Disable a specialty module (with optimistic update) */
  disableSpecialty: (specialty: SpecialtyType) => Promise<void>;
  /** Set primary specialty (onboarding) */
  setPrimarySpecialty: (specialty: SpecialtyType) => Promise<void>;
  /** Refresh customer data from server */
  refreshCustomer: () => Promise<void>;
}

const CustomerContext = createContext<CustomerContextValue | undefined>(undefined);

interface CustomerProviderProps {
  children: ReactNode;
}

// API base URL from environment
const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

// Helper to get auth headers
function getAuthHeaders(): HeadersInit {
  const token = localStorage.getItem('upstream_access_token');
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

export function CustomerProvider({ children }: CustomerProviderProps) {
  const [customer, setCustomer] = useState<CustomerProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch customer profile
  const fetchCustomer = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`${API_BASE}/customers/me/`, {
        headers: getAuthHeaders(),
      });

      if (!response.ok) {
        if (response.status === 401) {
          // Not authenticated, don't show error
          setCustomer(null);
          return;
        }
        throw new Error(`Failed to fetch customer: ${response.statusText}`);
      }

      const data = await response.json();
      setCustomer(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load customer';
      setError(message);
      console.error('Failed to fetch customer:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial fetch
  useEffect(() => {
    fetchCustomer();
  }, [fetchCustomer]);

  // Check if specialty is enabled
  const hasSpecialty = useCallback(
    (specialty: SpecialtyType | string): boolean => {
      if (!customer) return false;
      const code = specialty.toUpperCase() as SpecialtyType;
      return customer.enabled_specialties.includes(code);
    },
    [customer]
  );

  // Enable specialty with optimistic update
  const enableSpecialty = useCallback(
    async (specialty: SpecialtyType): Promise<void> => {
      if (!customer) {
        throw new Error('No customer loaded');
      }

      // Store previous state for rollback
      const previousCustomer = { ...customer };

      // Optimistic update
      setCustomer((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          enabled_specialties: [...prev.enabled_specialties, specialty],
          specialty_modules: [
            ...prev.specialty_modules,
            {
              id: Date.now(), // Temporary ID
              specialty,
              enabled: true,
              enabled_at: new Date().toISOString(),
              is_primary: false,
            },
          ],
        };
      });

      try {
        const response = await fetch(`${API_BASE}/customers/enable_specialty/`, {
          method: 'POST',
          headers: getAuthHeaders(),
          body: JSON.stringify({ specialty }),
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.error || `Failed to enable ${specialty}`);
        }

        // Refresh with server data
        const data = await response.json();
        setCustomer(data);
        toast.success(`${specialty} module enabled`);
      } catch (err) {
        // Rollback on error
        setCustomer(previousCustomer);
        const message = err instanceof Error ? err.message : `Failed to enable ${specialty}`;
        toast.error(message);
        throw err;
      }
    },
    [customer]
  );

  // Disable specialty with optimistic update
  const disableSpecialty = useCallback(
    async (specialty: SpecialtyType): Promise<void> => {
      if (!customer) {
        throw new Error('No customer loaded');
      }

      // Cannot disable primary specialty
      if (customer.specialty_type === specialty) {
        toast.error('Cannot disable primary specialty');
        throw new Error('Cannot disable primary specialty');
      }

      // Store previous state for rollback
      const previousCustomer = { ...customer };

      // Optimistic update
      setCustomer((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          enabled_specialties: prev.enabled_specialties.filter((s) => s !== specialty),
          specialty_modules: prev.specialty_modules.map((m) =>
            m.specialty === specialty ? { ...m, enabled: false } : m
          ),
        };
      });

      try {
        const response = await fetch(`${API_BASE}/customers/disable_specialty/`, {
          method: 'POST',
          headers: getAuthHeaders(),
          body: JSON.stringify({ specialty }),
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.error || `Failed to disable ${specialty}`);
        }

        // Refresh with server data
        const data = await response.json();
        setCustomer(data);
        toast.success(`${specialty} module disabled`);
      } catch (err) {
        // Rollback on error
        setCustomer(previousCustomer);
        const message = err instanceof Error ? err.message : `Failed to disable ${specialty}`;
        toast.error(message);
        throw err;
      }
    },
    [customer]
  );

  // Set primary specialty (onboarding)
  const setPrimarySpecialty = useCallback(
    async (specialty: SpecialtyType): Promise<void> => {
      // Store previous state for rollback
      const previousCustomer = customer ? { ...customer } : null;

      // Optimistic update
      setCustomer((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          specialty_type: specialty,
          enabled_specialties: [specialty],
          specialty_modules: [
            {
              id: Date.now(),
              specialty,
              enabled: true,
              enabled_at: new Date().toISOString(),
              is_primary: true,
            },
          ],
        };
      });

      try {
        const response = await fetch(`${API_BASE}/customers/set_primary_specialty/`, {
          method: 'POST',
          headers: getAuthHeaders(),
          body: JSON.stringify({ specialty_type: specialty }),
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.error || 'Failed to set primary specialty');
        }

        // Refresh with server data
        const data = await response.json();
        setCustomer(data);
        toast.success(`Primary specialty set to ${specialty}`);
      } catch (err) {
        // Rollback on error
        if (previousCustomer) {
          setCustomer(previousCustomer);
        }
        const message = err instanceof Error ? err.message : 'Failed to set primary specialty';
        toast.error(message);
        throw err;
      }
    },
    [customer]
  );

  const value: CustomerContextValue = {
    customer,
    loading,
    error,
    hasSpecialty,
    enableSpecialty,
    disableSpecialty,
    setPrimarySpecialty,
    refreshCustomer: fetchCustomer,
  };

  return <CustomerContext.Provider value={value}>{children}</CustomerContext.Provider>;
}

export function useCustomer(): CustomerContextValue {
  const context = useContext(CustomerContext);
  if (context === undefined) {
    throw new Error('useCustomer must be used within a CustomerProvider');
  }
  return context;
}

// Export specialty labels for UI
export const SPECIALTY_LABELS: Record<SpecialtyType, string> = {
  DIALYSIS: 'Dialysis',
  ABA: 'ABA Therapy',
  PTOT: 'PT/OT',
  IMAGING: 'Imaging',
  HOME_HEALTH: 'Home Health',
};

// Export specialty descriptions
export const SPECIALTY_DESCRIPTIONS: Record<SpecialtyType, string> = {
  DIALYSIS: 'MA payment variance detection',
  ABA: 'Authorization tracking & unit monitoring',
  PTOT: '8-minute rule & G-code validation',
  IMAGING: 'Prior auth requirements & RBM tracking',
  HOME_HEALTH: 'PDGM validation & F2F tracking',
};
