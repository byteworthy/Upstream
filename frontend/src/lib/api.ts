import axios, { type AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios';
import { toast } from 'sonner';
import {
  getAccessToken,
  getRefreshToken,
  setTokens,
  clearTokens,
  shouldRefreshToken,
} from './auth';
import type {
  AuthTokens,
  User,
  LoginRequest,
  Claim,
  ClaimScore,
  ClaimScoreListParams,
  Alert,
  AlertListParams,
  AutomationProfile,
  ExecutionLog,
  DashboardMetrics,
  Authorization,
  PaginatedResponse,
} from '@/types/api';

// Create axios instance with base configuration
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Track if we're currently refreshing the token
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (token: string) => void;
  reject: (error: Error) => void;
}> = [];

const processQueue = (error: Error | null, token: string | null = null) => {
  failedQueue.forEach((promise) => {
    if (error) {
      promise.reject(error);
    } else if (token) {
      promise.resolve(token);
    }
  });
  failedQueue = [];
};

// Request interceptor to add Authorization header
apiClient.interceptors.request.use(
  async (config: InternalAxiosRequestConfig) => {
    const accessToken = getAccessToken();

    if (accessToken) {
      // Check if token needs refresh before making request
      if (shouldRefreshToken(accessToken) && !config.url?.includes('/token/refresh')) {
        const refreshToken = getRefreshToken();
        if (refreshToken && !isRefreshing) {
          isRefreshing = true;
          try {
            const response = await axios.post<AuthTokens>(`${config.baseURL}/token/refresh/`, {
              refresh: refreshToken,
            });
            setTokens(response.data);
            config.headers.Authorization = `Bearer ${response.data.access}`;
            processQueue(null, response.data.access);
          } catch (error) {
            processQueue(error as Error);
            clearTokens();
            window.location.href = '/login';
            return Promise.reject(error);
          } finally {
            isRefreshing = false;
          }
        }
      } else {
        config.headers.Authorization = `Bearer ${accessToken}`;
      }
    }

    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor to handle 401 errors and refresh token
apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    // If error is 401 and we haven't retried yet
    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        // If already refreshing, queue this request
        return new Promise((resolve, reject) => {
          failedQueue.push({
            resolve: (token: string) => {
              originalRequest.headers.Authorization = `Bearer ${token}`;
              resolve(apiClient(originalRequest));
            },
            reject: (err: Error) => {
              reject(err);
            },
          });
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      const refreshToken = getRefreshToken();
      if (!refreshToken) {
        clearTokens();
        window.location.href = '/login';
        return Promise.reject(error);
      }

      try {
        const response = await axios.post<AuthTokens>(`${originalRequest.baseURL}/token/refresh/`, {
          refresh: refreshToken,
        });
        setTokens(response.data);
        originalRequest.headers.Authorization = `Bearer ${response.data.access}`;
        processQueue(null, response.data.access);
        return apiClient(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError as Error);
        clearTokens();
        window.location.href = '/login';
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    // Handle other errors with toast notifications
    const message = getErrorMessage(error);
    if (error.response?.status !== 401) {
      toast.error(message);
    }

    return Promise.reject(error);
  }
);

function getErrorMessage(error: AxiosError): string {
  if (error.response?.data) {
    const data = error.response.data as Record<string, unknown>;
    if (typeof data === 'string') return data;
    if (data.detail) return String(data.detail);
    if (data.message) return String(data.message);
    if (data.error) return String(data.error);
  }
  if (error.message) return error.message;
  return 'An unexpected error occurred';
}

// Auth API
export const authApi = {
  login: async (credentials: LoginRequest): Promise<AuthTokens> => {
    const response = await apiClient.post<AuthTokens>('/token/', credentials);
    setTokens(response.data);
    return response.data;
  },

  logout: async (): Promise<void> => {
    clearTokens();
  },

  refreshToken: async (refreshToken: string): Promise<AuthTokens> => {
    const response = await apiClient.post<AuthTokens>('/token/refresh/', {
      refresh: refreshToken,
    });
    setTokens(response.data);
    return response.data;
  },

  getCurrentUser: async (): Promise<User> => {
    const response = await apiClient.get<User>('/users/me/');
    return response.data;
  },
};

// Claims API
export const claimsApi = {
  list: async (params?: ClaimScoreListParams): Promise<PaginatedResponse<Claim>> => {
    const response = await apiClient.get<PaginatedResponse<Claim>>('/claims/', { params });
    return response.data;
  },

  get: async (id: number): Promise<Claim> => {
    const response = await apiClient.get<Claim>(`/claims/${id}/`);
    return response.data;
  },
};

// ClaimScores API
export const claimScoresApi = {
  list: async (params?: ClaimScoreListParams): Promise<PaginatedResponse<ClaimScore>> => {
    const response = await apiClient.get<PaginatedResponse<ClaimScore>>('/claim-scores/', {
      params,
    });
    return response.data;
  },

  get: async (id: number): Promise<ClaimScore> => {
    const response = await apiClient.get<ClaimScore>(`/claim-scores/${id}/`);
    return response.data;
  },

  score: async (claimId: number): Promise<ClaimScore> => {
    const response = await apiClient.post<ClaimScore>(`/claims/${claimId}/score/`);
    return response.data;
  },
};

// Alerts API
export const alertsApi = {
  list: async (params?: AlertListParams): Promise<PaginatedResponse<Alert>> => {
    const response = await apiClient.get<PaginatedResponse<Alert>>('/alerts/', { params });
    return response.data;
  },

  get: async (id: number): Promise<Alert> => {
    const response = await apiClient.get<Alert>(`/alerts/${id}/`);
    return response.data;
  },

  acknowledge: async (id: number): Promise<Alert> => {
    const response = await apiClient.post<Alert>(`/alerts/${id}/acknowledge/`);
    return response.data;
  },

  resolve: async (id: number, resolutionNotes?: string): Promise<Alert> => {
    const response = await apiClient.post<Alert>(`/alerts/${id}/resolve/`, {
      resolution_notes: resolutionNotes,
    });
    return response.data;
  },

  markAsNoise: async (id: number): Promise<Alert> => {
    const response = await apiClient.post<Alert>(`/alerts/${id}/mark-as-noise/`);
    return response.data;
  },
};

// Automation Profile API
export const automationProfileApi = {
  get: async (): Promise<AutomationProfile> => {
    const response = await apiClient.get<AutomationProfile>('/automation-profile/');
    return response.data;
  },

  update: async (data: Partial<AutomationProfile>): Promise<AutomationProfile> => {
    const response = await apiClient.patch<AutomationProfile>('/automation-profile/', data);
    return response.data;
  },
};

// Execution Log API
export const executionLogApi = {
  list: async (params?: {
    page?: number;
    page_size?: number;
    action?: string;
    result?: string;
    executed_after?: string;
    executed_before?: string;
  }): Promise<PaginatedResponse<ExecutionLog>> => {
    const response = await apiClient.get<PaginatedResponse<ExecutionLog>>('/execution-logs/', {
      params,
    });
    return response.data;
  },

  get: async (id: number): Promise<ExecutionLog> => {
    const response = await apiClient.get<ExecutionLog>(`/execution-logs/${id}/`);
    return response.data;
  },
};

// Dashboard API
export const dashboardApi = {
  getMetrics: async (): Promise<DashboardMetrics> => {
    const response = await apiClient.get<DashboardMetrics>('/dashboard/metrics/');
    return response.data;
  },
};

// Authorizations API (Home Health)
export const authorizationsApi = {
  list: async (params?: {
    page?: number;
    page_size?: number;
    status?: string;
    expiring_before?: string;
  }): Promise<PaginatedResponse<Authorization>> => {
    const response = await apiClient.get<PaginatedResponse<Authorization>>('/authorizations/', {
      params,
    });
    return response.data;
  },

  get: async (id: number): Promise<Authorization> => {
    const response = await apiClient.get<Authorization>(`/authorizations/${id}/`);
    return response.data;
  },
};

// Work Queue API (Tier 2 claims)
export const workQueueApi = {
  list: async (params?: {
    page?: number;
    page_size?: number;
    ordering?: string;
  }): Promise<PaginatedResponse<ClaimScore>> => {
    const response = await apiClient.get<PaginatedResponse<ClaimScore>>('/work-queue/', { params });
    return response.data;
  },

  approve: async (id: number): Promise<ExecutionLog> => {
    const response = await apiClient.post<ExecutionLog>(`/work-queue/${id}/approve/`);
    return response.data;
  },

  reject: async (id: number, reason?: string): Promise<ExecutionLog> => {
    const response = await apiClient.post<ExecutionLog>(`/work-queue/${id}/reject/`, { reason });
    return response.data;
  },

  escalate: async (id: number, reason?: string): Promise<ExecutionLog> => {
    const response = await apiClient.post<ExecutionLog>(`/work-queue/${id}/escalate/`, { reason });
    return response.data;
  },

  bulkApprove: async (ids: number[]): Promise<ExecutionLog[]> => {
    const response = await apiClient.post<ExecutionLog[]>('/work-queue/bulk-approve/', { ids });
    return response.data;
  },

  bulkReject: async (ids: number[], reason?: string): Promise<ExecutionLog[]> => {
    const response = await apiClient.post<ExecutionLog[]>('/work-queue/bulk-reject/', {
      ids,
      reason,
    });
    return response.data;
  },
};

export default apiClient;
