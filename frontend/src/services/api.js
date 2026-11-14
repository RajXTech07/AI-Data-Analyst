/**
 * API Service Client for AI Data Analyst FastAPI Backend
 * Base URL: /api/v1 (proxied by Vite to http://localhost:8000)
 */

const rawHost = import.meta.env.VITE_API_BASE_URL || (import.meta.env.PROD ? 'https://ai-data-analyst-6y46.onrender.com' : '');
const API_HOST = (rawHost || '').trim().replace(/\/+$/, '');
const API_BASE = API_HOST ? `${API_HOST}/api/v1` : '/api/v1';

class ApiClient {
  constructor() {
    this.token = localStorage.getItem('auth_token') || null;
  }

  setToken(token) {
    this.token = token;
    if (token) {
      localStorage.setItem('auth_token', token);
    } else {
      localStorage.removeItem('auth_token');
    }
  }

  getHeaders(isMultipart = false) {
    const headers = {};
    if (!isMultipart) {
      headers['Content-Type'] = 'application/json';
    }
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }
    return headers;
  }

  async request(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const isMultipart = options.body instanceof FormData;
    const headers = { ...this.getHeaders(isMultipart), ...(options.headers || {}) };

    try {
      const response = await fetch(url, { ...options, headers });
      if (!response.ok) {
        let errMessage = `HTTP ${response.status}: ${response.statusText}`;
        try {
          const errorJson = await response.json();
          errMessage = errorJson.detail || errorJson.message || errMessage;
        } catch {
          // ignore parsing error
        }
        throw new Error(errMessage);
      }
      return await response.json();
    } catch (err) {
      console.warn(`[API] Call to ${endpoint} failed:`, err.message);
      throw err;
    }
  }

  // Health check
  async checkHealth() {
    return this.request('/health');
  }

  // Dataset Endpoints
  async uploadDataset(file) {
    const formData = new FormData();
    formData.append('file', file);
    return this.request('/datasets/upload', {
      method: 'POST',
      body: formData,
    });
  }

  async loadSampleDataset(sampleName = 'movies_messy.csv') {
    return this.request(`/datasets/sample?sample_name=${sampleName}`, {
      method: 'POST',
    });
  }

  async listDatasets() {
    return this.request('/datasets');
  }

  async getDataset(id) {
    return this.request(`/datasets/${id}`);
  }

  async getDatasetProfile(id) {
    return this.request(`/datasets/${id}/profile`);
  }

  async getDatasetPreview(id, rows = 20) {
    return this.request(`/datasets/${id}/preview?rows=${rows}`);
  }

  async getDatasetIssues(id) {
    return this.request(`/datasets/${id}/issues`);
  }

  async cleanDataset(id, selectedFixes = []) {
    return this.request(`/datasets/${id}/clean`, {
      method: 'POST',
      body: JSON.stringify({ selected_fixes: selectedFixes }),
    });
  }

  async downloadCleanedCSV(id) {
    const url = `${API_BASE}/datasets/${id}/clean/download`;
    const headers = this.getHeaders();
    const res = await fetch(url, { headers });
    if (!res.ok) throw new Error('Failed to download cleaned CSV');
    return await res.blob();
  }

  // Autonomous Analysis Endpoints
  async startAnalysis(datasetId, options = {}) {
    return this.request(`/datasets/${datasetId}/analyze`, {
      method: 'POST',
      body: JSON.stringify({
        question: options.question || null,
        options: {
          exclude_incomplete_rows: options.exclude_incomplete_rows || false,
          filters: options.filters || [],
        },
      }),
    });
  }

  async getAnalysis(analysisId) {
    return this.request(`/analyses/${analysisId}`);
  }

  async getFindings(analysisId) {
    return this.request(`/analyses/${analysisId}/findings`);
  }

  async getCharts(analysisId) {
    return this.request(`/analyses/${analysisId}/charts`);
  }

  async getToolExecutions(analysisId) {
    return this.request(`/analyses/${analysisId}/tool-executions`);
  }

  async generateReport(analysisId, format = 'html') {
    return this.request(`/analyses/${analysisId}/report`, {
      method: 'POST',
      body: JSON.stringify({ format }),
    });
  }

  async sendChatMessage(analysisId, message) {
    return this.request(`/analyses/${analysisId}/chat`, {
      method: 'POST',
      body: JSON.stringify({ message }),
    });
  }

  // Authentication
  async login(email, password) {
    const res = await this.request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    if (res.access_token) {
      this.setToken(res.access_token);
    }
    return res;
  }

  async register(email, password, fullName = '') {
    return this.request('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, full_name: fullName }),
    });
  }

  async getMe() {
    return this.request('/auth/me');
  }

  logout() {
    this.setToken(null);
  }
}

export const api = new ApiClient();

