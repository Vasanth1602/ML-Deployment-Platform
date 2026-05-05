/**
 * Application constants
 */

// API Configuration
// In production (Docker + Nginx), VITE_API_URL is not set at build time so this
// resolves to '' — all /api/* calls are relative and proxied by Nginx to the backend.
// In local dev without Docker, set VITE_API_URL=http://localhost:5000 in .env.local
export const API_BASE_URL = import.meta.env.VITE_API_URL ?? '';

// Deployment Steps — must match step names emitted by deployment_orchestrator.py
export const DEPLOYMENT_STEPS = [
    'Validation',
    'EC2 Creation',
    'EC2 Readiness',
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
