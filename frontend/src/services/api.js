/**
 * API Service Layer
 * Handles all HTTP requests to the Flask backend.
 * Automatically attaches JWT Bearer token from localStorage.
 * Redirects to /login on 401 (token expired or missing).
 */

import { API_BASE_URL } from '../utils/constants';

const TOKEN_KEY = 'ml_deploy_token';

class ApiService {
    constructor() {
        this.baseURL = API_BASE_URL;
    }

    /**
     * Generic fetch wrapper.
     * - Auto-attaches Authorization: Bearer <token> header if a token exists.
     * - On 401: clears the stored token and redirects to /login.
     */
    async request(endpoint, options = {}) {
        const url   = `${this.baseURL}${endpoint}`;
        const token = localStorage.getItem(TOKEN_KEY);

        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...(token ? { Authorization: `Bearer ${token}` } : {}),
                ...options.headers,
            },
            ...options,
        };

        const response = await fetch(url, config);

        // Handle 401 — token expired or tampered with
        if (response.status === 401) {
            localStorage.removeItem(TOKEN_KEY);
            // Only redirect if not already on an auth page to avoid loop
            if (!window.location.pathname.startsWith('/login') &&
                !window.location.pathname.startsWith('/register')) {
                window.location.href = '/login';
            }
        }

        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
            throw new Error(data.error || `HTTP error! status: ${response.status}`);
        }

        return data;
    }

    // ── Auth ──────────────────────────────────────────────────────────────────

    async login({ email, password }) {
        return this.request('/api/auth/login', {
            method: 'POST',
            body: JSON.stringify({ email, password }),
        });
    }

    async register({ email, password }) {
        return this.request('/api/auth/register', {
            method: 'POST',
            body: JSON.stringify({ email, password }),
        });
    }

    async logout() {
        return this.request('/api/auth/logout', { method: 'POST' });
    }

    async getMe() {
        return this.request('/api/auth/me');
    }

    // ── Health ────────────────────────────────────────────────────────────────

    async healthCheck() {
        return this.request('/api/health');
    }

    // ── Deployments ───────────────────────────────────────────────────────────

    async deploy(deploymentData) {
        return this.request('/api/deploy', {
            method: 'POST',
            body: JSON.stringify(deploymentData),
        });
    }

    async getDeployments(params = {}) {
        const qs = new URLSearchParams(params).toString();
        return this.request(`/api/deployments${qs ? '?' + qs : ''}`);
    }

    async getDeployment(deploymentId) {
        return this.request(`/api/deployments/${deploymentId}`);
    }

    async cancelDeployment(deploymentId) {
        return this.request(`/api/deployments/${deploymentId}/cancel`, {
            method: 'POST',
        });
    }

    // ── Applications ──────────────────────────────────────────────────────────

    async getApplications() {
        return this.request('/api/applications');
    }

    async getApplication(appId) {
        return this.request(`/api/applications/${appId}`);
    }

    // ── Instances ─────────────────────────────────────────────────────────────

    async getInstances() {
        return this.request('/api/instances');
    }

    async stopInstance(instanceId) {
        return this.request(`/api/instances/${instanceId}/stop`, { method: 'POST' });
    }

    async startInstance(instanceId) {
        return this.request(`/api/instances/${instanceId}/start`, { method: 'POST' });
    }

    async terminateInstance(instanceId) {
        return this.request(`/api/instances/${instanceId}/terminate`, { method: 'POST' });
    }

    async syncInstances() {
        return this.request('/api/instances/sync', { method: 'POST' });
    }

    // ── Stats ─────────────────────────────────────────────────────────────────

    async getStats() {
        return this.request('/api/stats');
    }

    // ── Config ────────────────────────────────────────────────────────────────

    async validateConfig() {
        return this.request('/api/config/validate');
    }
}

export const api = new ApiService();
