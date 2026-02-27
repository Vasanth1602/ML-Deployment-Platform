/**
 * API Service Layer
 * Handles all HTTP requests to the Flask backend
 * Centralizes error handling and response formatting
 */

import { API_BASE_URL } from '../utils/constants';

class ApiService {
    constructor() {
        this.baseURL = API_BASE_URL;
    }

    /**
     * Generic fetch wrapper with error handling
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers,
            },
            ...options,
        };

        try {
            const response = await fetch(url, config);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || `HTTP error! status: ${response.status}`);
            }

            return data;
        } catch (error) {
            console.error(`API Error [${endpoint}]:`, error);
            throw error;
        }
    }

    // Health Check
    async healthCheck() {
        return this.request('/api/health');
    }

    // Deployment Endpoints
    async deploy(deploymentData) {
        return this.request('/api/deploy', {
            method: 'POST',
            body: JSON.stringify(deploymentData),
        });
    }

    async getDeployments() {
        return this.request('/api/deployments');
    }

    async getDeployment(deploymentId) {
        return this.request(`/api/deployments/${deploymentId}`);
    }

    // Applications Endpoints
    async getApplications() {
        return this.request('/api/applications');
    }

    // Instance Endpoints
    async getInstances() {
        return this.request('/api/instances');
    }

    async stopInstance(instanceId) {
        return this.request(`/api/instances/${instanceId}/stop`, {
            method: 'POST',
        });
    }

    async startInstance(instanceId) {
        return this.request(`/api/instances/${instanceId}/start`, {
            method: 'POST',
        });
    }

    async terminateInstance(instanceId) {
        return this.request(`/api/instances/${instanceId}/terminate`, {
            method: 'POST',
        });
    }

    // Configuration
    async validateConfig() {
        return this.request('/api/config/validate');
    }

    // Stats Endpoint
    async getStats() {
        return this.request('/api/stats');
    }
}

// Export singleton instance
export const api = new ApiService();
