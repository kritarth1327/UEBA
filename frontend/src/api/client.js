/**
 * Centralized API Client for UEBA Backend Services
 */

const BASE_URL = import.meta.env.VITE_API_URL || '';
const API_PREFIX = '/api/v1';

class ApiError extends Error {
  constructor(message, status, data = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

async function request(endpoint, options = {}) {
  const { params, signal, ...customConfig } = options;
  let url = `${BASE_URL}${API_PREFIX}${endpoint}`;

  if (params) {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, val]) => {
      if (val !== undefined && val !== null && val !== '') {
        query.append(key, val);
      }
    });
    const queryString = query.toString();
    if (queryString) {
      url += `?${queryString}`;
    }
  }

  const headers = {
    'Content-Type': 'application/json',
    ...(customConfig.headers || {}),
  };

  const config = {
    ...customConfig,
    headers,
    signal,
  };

  try {
    const response = await fetch(url, config);
    if (!response.ok) {
      let errorData = null;
      try {
        errorData = await response.json();
      } catch {
        // Response was not JSON
      }
      const message = errorData?.detail || errorData?.message || `Request failed with status ${response.status}`;
      throw new ApiError(message, response.status, errorData);
    }

    if (response.status === 204) {
      return null;
    }

    return await response.json();
  } catch (err) {
    if (err.name === 'AbortError') {
      throw err; // Let consumer handle abortion
    }
    if (err instanceof ApiError) {
      throw err;
    }
    throw new ApiError(err.message || 'Network connection failed', 0);
  }
}

export const api = {
  // Health & System
  getHealth: (signal) => request('/health', { signal }),
  getSystemStatus: (signal) => request('/system/status', { signal }),

  // Dashboard
  getDashboardOverview: (signal) => request('/dashboard/overview', { signal }),

  // Users
  getUsers: (params, signal) => request('/users', { params, signal }),
  getUserDetail: (userId, signal) => request(`/users/${encodeURIComponent(userId)}`, { signal }),
  getUserBehavior: (userId, params, signal) =>
    request(`/users/${encodeURIComponent(userId)}/behavior`, { params, signal }),
  getUserRisk: (userId, params, signal) =>
    request(`/users/${encodeURIComponent(userId)}/risk`, { params, signal }),

  // Alerts
  getAlerts: (params, signal) => request('/alerts', { params, signal }),
  getAlertDetail: (alertId, signal) => request(`/alerts/${encodeURIComponent(alertId)}`, { signal }),
  updateAlertStatus: (alertId, data) =>
    request(`/alerts/${encodeURIComponent(alertId)}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  // Models & Evaluation
  getModelsStatus: (signal) => request('/models/status', { signal }),
  getModelsEvaluation: (signal) => request('/models/evaluation', { signal }),
};

export { ApiError };
