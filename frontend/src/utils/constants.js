/**
 * Application constants
 */

// API Configuration
export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

// Deployment Steps
export const DEPLOYMENT_STEPS = [
    'Validation',
    'EC2 Creation',
    'SSH Connection',
    'Docker Installation',
    'NGINX Installation',
    'Repository Clone',
    'Project Validation',
    'Docker Build',
    'Container Deployment',
    'NGINX Configuration',
    'Health Check',
    'Deployment Complete'
];

// Status Types
export const STATUS = {
    PENDING: 'pending',
    IN_PROGRESS: 'in_progress',
    SUCCESS: 'success',
    FAILED: 'failed',
    WARNING: 'warning'
};

// Instance States
export const INSTANCE_STATES = {
    RUNNING: 'running',
    STOPPED: 'stopped',
    PENDING: 'pending',
    STOPPING: 'stopping',
    TERMINATED: 'terminated'
};

// Toast Types
export const TOAST_TYPES = {
    SUCCESS: 'success',
    ERROR: 'error',
    INFO: 'info',
    WARNING: 'warning'
};
