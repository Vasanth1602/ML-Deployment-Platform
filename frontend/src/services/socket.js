/**
 * WebSocket Service Layer
 * Manages Socket.IO connection for real-time deployment updates
 * Provides event subscription and cleanup mechanisms
 */

import { io } from 'socket.io-client';
import { API_BASE_URL } from '../utils/constants';

const TOKEN_KEY = 'ml_deploy_token';

class SocketService {
    constructor() {
        this.socket = null;
        this.connected = false;
    }

    /**
     * Initialize WebSocket connection
     */
    connect() {
        if (this.socket?.connected) {
            return this.socket;
        }

        // Pass JWT via query param — backend's connect handler verifies it
        // and calls disconnect() if it is missing, expired, or invalid.
        const token = localStorage.getItem(TOKEN_KEY);

        this.socket = io(API_BASE_URL, {
            transports: ['websocket', 'polling'],
            reconnection: true,
            reconnectionDelay: 1000,
            reconnectionAttempts: 10,
            timeout: 20000,
            pingTimeout: 300000,
            pingInterval: 25000,
            ...(token ? { query: { token } } : {}),
        });

        this.socket.on('connect', () => {
            console.log('✅ WebSocket connected');
            this.connected = true;
        });

        this.socket.on('disconnect', (reason) => {
            console.log('❌ WebSocket disconnected:', reason);
            this.connected = false;
        });

        this.socket.on('connect_error', (error) => {
            console.error('WebSocket connection error:', error);
        });

        this.socket.on('reconnect', (attemptNumber) => {
            console.log(`🔄 WebSocket reconnected after ${attemptNumber} attempts`);
        });

        return this.socket;
    }

    /**
     * Disconnect WebSocket
     */
    disconnect() {
        if (this.socket) {
            this.socket.disconnect();
            this.socket = null;
            this.connected = false;
        }
    }

    /**
     * Subscribe to deployment progress updates
     */
    onDeploymentProgress(callback) {
        if (!this.socket) this.connect();
        this.socket.on('deployment_progress', callback);
    }

    /**
     * Subscribe to deployment completion
     */
    onDeploymentComplete(callback) {
        if (!this.socket) this.connect();
        this.socket.on('deployment_complete', callback);
    }

    /**
     * Unsubscribe from deployment progress
     */
    offDeploymentProgress(callback) {
        if (this.socket) {
            this.socket.off('deployment_progress', callback);
        }
    }

    /**
     * Unsubscribe from deployment completion
     */
    offDeploymentComplete(callback) {
        if (this.socket) {
            this.socket.off('deployment_complete', callback);
        }
    }

    /**
     * Subscribe to deployment_cancelled — emitted by the backend when the
     * orchestrator's DeploymentCancelled exception handler finishes cleanup.
     */
    onDeploymentCancelled(callback) {
        if (!this.socket) this.connect();
        this.socket.on('deployment_cancelled', callback);
    }

    /**
     * Unsubscribe from deployment_cancelled
     */
    offDeploymentCancelled(callback) {
        if (this.socket) {
            this.socket.off('deployment_cancelled', callback);
        }
    }

    /**
     * Subscribe to a specific deployment
     */
    subscribeToDeployment(deploymentId) {
        if (!this.socket) this.connect();
        this.socket.emit('subscribe_deployment', { deployment_id: deploymentId });
    }

    /**
     * Check connection status
     */
    isConnected() {
        return this.connected && this.socket?.connected;
    }

    /**
     * Get socket instance (for debugging)
     */
    getSocket() {
        return this.socket;
    }
}

// Export singleton instance
export const socket = new SocketService();
