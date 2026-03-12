/**
 * Application constants
 */

// API Configuration
// Empty string = relative URLs (/api/...) — works with ALB routing in ECS.
// Set VITE_API_URL at build time only if calling a completely separate host.
export const API_BASE_URL = import.meta.env.VITE_API_URL || '';

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
    ACTIVE: 'active',
    FAILED: 'failed',
    CANCELLED: 'cancelled',
    STOPPED: 'stopped',
    TERMINATED: 'terminated',
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
