/**
 * WebSocket Service Layer
 * Manages Socket.IO connection for real-time deployment updates
 * Provides event subscription and cleanup mechanisms
 */

import { io } from 'socket.io-client';
import { API_BASE_URL } from '../utils/constants';

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

        this.socket = io(API_BASE_URL, {
            transports: ['polling'],  // Use polling only - more reliable for long operations
            reconnection: true,
            reconnectionDelay: 1000,
            reconnectionAttempts: 10,
            timeout: 20000,
            pingTimeout: 300000,  // 5 minutes - match backend
            pingInterval: 25000,  // 25 seconds - match backend
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
