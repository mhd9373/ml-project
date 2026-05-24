// src/utils/api.js - FoodWise AI API client

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8080/api/v1';

function getToken() {
  return localStorage.getItem('foodwise_token');
}

async function request(path, options = {}) {
  const token = getToken();
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ message: 'Unknown error' }));
    throw new Error(err.message || `HTTP ${res.status}`);
  }
  return res.json();
}

// ─── Auth ──────────────────────────────────────────────────────────────────
export const auth = {
  login: (email, password) =>
    request('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  register: (data) =>
    request('/auth/register', { method: 'POST', body: JSON.stringify(data) }),
};

// ─── Prediction ─────────────────────────────────────────────────────────────
export const prediction = {
  predict: (data) =>
    request('/predict-demand', { method: 'POST', body: JSON.stringify(data) }),
  bulkUpload: (file) => {
    const form = new FormData();
    form.append('file', file);
    return fetch(`${API_BASE}/predict-demand/bulk`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${getToken()}` },
      body: form,
    }).then(r => r.json());
  },
};

// ─── Analytics ──────────────────────────────────────────────────────────────
export const analytics = {
  getSummary: (days = 7, restaurant = null) => {
    const params = new URLSearchParams({ days });
    if (restaurant) params.append('restaurant', restaurant);
    return request(`/analytics?${params}`);
  },
  getRestaurants: (days = 30) => request(`/analytics/restaurants?days=${days}`),
  getCategories: () => request('/analytics/categories'),
};

// ─── History ────────────────────────────────────────────────────────────────
export const history = {
  getPage: (page = 0, size = 20, filters = {}) => {
    const params = new URLSearchParams({ page, size, ...filters });
    return request(`/history?${params}`);
  },
};

// ─── Export ─────────────────────────────────────────────────────────────────
export const exportData = {
  csv: async (days = 30) => {
    const res = await fetch(`${API_BASE}/export/csv?days=${days}`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `foodwise_${days}d.csv`; a.click();
  },
  excel: async (days = 30) => {
    const res = await fetch(`${API_BASE}/export/excel?days=${days}`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `foodwise_${days}d.xlsx`; a.click();
  },
};

export default { auth, prediction, analytics, history, exportData };
