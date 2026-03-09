import { useState, useEffect, useCallback, useRef } from 'react';
import { ArrowLeft, XCircle } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import DeploymentForm from '../components/DeploymentForm';
import ProgressTracker from '../components/ProgressTracker';
import { ToastContainer } from '../components/Toast';
import { useToast } from '../hooks/useToast';
import { api } from '../services/api';
import { socket } from '../services/socket';

// ─── Helpers ──────────────────────────────────────────────────────────────────

/**
 * Map the DB deployment record → the shape the ProgressTracker expects.
 * DB steps look like: { step_name, status, message }
 * UI steps look like: { step, status, message }
 */
function normaliseSteps(dbSteps = []) {
    return dbSteps.map(s => ({
        step: s.step_name ?? s.step ?? 'Unknown',
        status: s.status,
        message: s.message ?? '',
    }));
}

/**
 * Apply a single WebSocket progress event on top of the existing steps array.
 * Merges by step name so duplicates are updated in-place.
 */
function mergeStep(prev, data) {
    const idx = prev.findIndex(s => s.step === data.step);
    if (idx >= 0) {
        const updated = [...prev];
        updated[idx] = { step: data.step, message: data.message, status: data.status };
        return updated;
    }
    return [...prev, { step: data.step, message: data.message, status: data.status }];
}

// ─── Session-storage key for recovering after page refresh ───────────────────
const STORAGE_KEY = 'active_deployment_id';

// ─── Component ────────────────────────────────────────────────────────────────

export default function Deploy() {
    const navigate = useNavigate();
    const { toasts, removeToast, showSuccess, showError, showInfo } = useToast();

    const [isDeploying, setIsDeploying] = useState(false);
    const [deploymentSteps, setDeploymentSteps] = useState([]);
    const [deploymentStatus, setDeploymentStatus] = useState(null);   // null | 'in_progress' | 'success' | 'failed'
    const [deploymentResult, setDeploymentResult] = useState(null);
    const [deploymentId, setDeploymentId] = useState(null);   // short_id from backend
    const [isCancelling, setIsCancelling] = useState(false);

    // Ref so the polling interval can always read the latest deploymentId
    const deploymentIdRef = useRef(null);
    const pollingRef = useRef(null);

    // ── Apply API response to all state ────────────────────────────────────
    const applyApiState = useCallback((dep) => {
        if (!dep) return;

        const steps = normaliseSteps(dep.steps);
        const status = dep.status === 'success' ? 'success'
            : dep.status === 'failed' ? 'failed'
                : 'in_progress';

        setDeploymentSteps(steps);
        setDeploymentStatus(status);
        setIsDeploying(status === 'in_progress');

        if (status !== 'in_progress') {
            setDeploymentResult({
                success: status === 'success',
                url: dep.url,
                error: dep.error,
            });
        }
    }, []);

    // ── Poll the API once ────────────────────────────────────────────────
    const pollDeployment = useCallback(async (id) => {
        if (!id) return;
        try {
            const dep = await api.getDeployment(id);
            applyApiState(dep);

            // Stop polling once terminal
            if (dep.status === 'success' || dep.status === 'failed') {
                clearInterval(pollingRef.current);
                pollingRef.current = null;
                sessionStorage.removeItem(STORAGE_KEY);

                if (dep.status === 'success') {
                    showSuccess('Deployment completed successfully! 🎉', 7000);
                } else {
                    showError(`Deployment failed: ${dep.error || 'Unknown error'}`, 7000);
                }
            }
        } catch (err) {
            console.warn('[Deploy] API poll failed:', err.message);
        }
    }, [applyApiState, showSuccess, showError]);

    // ── Start / stop background polling ────────────────────────────────
    const startPolling = useCallback((id) => {
        if (pollingRef.current) return;   // already running
        pollingRef.current = setInterval(() => {
            // Only poll when WebSocket is disconnected or unreliable
            if (!socket.isConnected()) {
                pollDeployment(id);
            }
        }, 3000);
    }, [pollDeployment]);

    const stopPolling = useCallback(() => {
        if (pollingRef.current) {
            clearInterval(pollingRef.current);
            pollingRef.current = null;
        }
    }, []);

    // ── On mount: restore in-progress deployment ───────────────────────
    // Stage 1: sessionStorage fast-path (deployment_id was returned by backend)
    // Stage 2: API fallback — query for the latest in_progress deployment
    //          (handles case where backend didn't return deployment_id)
    useEffect(() => {
        const restoreDeployment = async () => {
            // Stage 1 — saved ID from the POST response
            const savedId = sessionStorage.getItem(STORAGE_KEY);
            if (savedId) {
                console.log('[Deploy] Restoring from sessionStorage:', savedId);
                deploymentIdRef.current = savedId;
                setDeploymentId(savedId);
                setDeploymentStatus('in_progress');
                setIsDeploying(true);
                await pollDeployment(savedId);
                startPolling(savedId);
                return;
            }

            // Stage 2 — no saved ID: check if there's an in-progress deployment in DB
            try {
                const result = await api.getDeployments({ status: 'in_progress', limit: 1 });
                const deps = result.deployments || [];
                if (deps.length > 0) {
                    const latest = deps[0];
                    const id = latest.short_id;
                    console.log('[Deploy] Found in-progress deployment from API:', id);
                    deploymentIdRef.current = id;
                    setDeploymentId(id);
                    setDeploymentStatus('in_progress');
                    setIsDeploying(true);
                    sessionStorage.setItem(STORAGE_KEY, id);   // save for future refreshes
                    await pollDeployment(id);
                    startPolling(id);
                }
            } catch (err) {
                console.warn('[Deploy] Could not check for in-progress deployments:', err.message);
            }
        };

        restoreDeployment();
        return () => stopPolling();
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    // ── WebSocket: deployment_progress ─────────────────────────────────
    const handleDeploymentProgress = useCallback((data) => {
        console.log('📡 WS progress:', data);
        setDeploymentSteps(prev => mergeStep(prev, data));
    }, []);

    // ── WebSocket: deployment_complete ─────────────────────────────────
    const handleDeploymentComplete = useCallback((data) => {
        console.log('✅ WS complete:', data);

        stopPolling();
        sessionStorage.removeItem(STORAGE_KEY);

        setIsDeploying(false);
        setDeploymentStatus(data.success ? 'success' : 'failed');
        // Preserve cancelled flag so ProgressTracker can show the right UI
        setDeploymentResult(data);

        if (data.success) {
            showSuccess('Deployment completed successfully! 🎉', 7000);
        } else if (data.cancelled) {
            showInfo('Deployment was cancelled.', 5000);
        } else {
            showError(`Deployment failed: ${data.error || 'Unknown error'}`, 7000);
        }

        // Fetch final state from API to ensure steps are complete
        const id = deploymentIdRef.current;
        if (id) pollDeployment(id);
    }, [stopPolling, pollDeployment, showSuccess, showError, showInfo]);

    // ── WebSocket: deployment_cancelled ────────────────────────────────
    // Emitted by the orchestrator after cleanup is fully done (EC2 terminated,
    // DB updated). Server-authoritative signal that cancel is complete.
    const handleDeploymentCancelled = useCallback((data) => {
        console.log('🛑 WS cancelled:', data);

        stopPolling();
        sessionStorage.removeItem(STORAGE_KEY);

        setIsDeploying(false);
        setIsCancelling(false);
        setDeploymentStatus('failed');
        setDeploymentResult({ ...data, cancelled: true });

        showInfo('Deployment cancelled. AWS resources cleaned up.', 6000);

        // Refresh steps from DB so the 'Cancelled' step row is visible
        const id = deploymentIdRef.current;
        if (id) pollDeployment(id);
    }, [stopPolling, pollDeployment, showInfo]);

    // ── Attach WebSocket listeners ──────────────────────────────────────
    useEffect(() => {
        console.log('🔌 Setting up WebSocket listeners...');
        socket.connect();

        const socketInstance = socket.getSocket();
        if (socketInstance) {
            socketInstance.onAny((eventName, ...args) => {
                console.log(`📡 WS event: ${eventName}`, args);
            });
        }

        socket.onDeploymentProgress(handleDeploymentProgress);
        socket.onDeploymentComplete(handleDeploymentComplete);
        socket.onDeploymentCancelled(handleDeploymentCancelled);
        console.log('✅ WebSocket listeners attached');

        return () => {
            console.log('🔌 Cleaning up WebSocket listeners...');
            socket.offDeploymentProgress(handleDeploymentProgress);
            socket.offDeploymentComplete(handleDeploymentComplete);
            socket.offDeploymentCancelled(handleDeploymentCancelled);
        };
    }, [handleDeploymentProgress, handleDeploymentComplete, handleDeploymentCancelled]);

    // ── Handle form submission ──────────────────────────────────────────
    const handleDeploy = async (formData) => {
        try {
            if (!socket.isConnected()) {
                console.log('⏳ WebSocket not connected, connecting...');
                socket.connect();
                await new Promise(resolve => setTimeout(resolve, 1000));
            }

            setIsDeploying(true);
            setDeploymentSteps([]);
            setDeploymentStatus('in_progress');
            setDeploymentResult(null);

            showInfo('Starting deployment...', 3000);

            const response = await api.deploy(formData);

            if (!response.success) {
                throw new Error(response.error || 'Failed to start deployment');
            }

            // Store deployment_id so WebSocket fallback polling can use it
            const id = response.deployment_id;
            if (id) {
                deploymentIdRef.current = id;
                setDeploymentId(id);
                sessionStorage.setItem(STORAGE_KEY, id);  // survive page refresh
                startPolling(id);
            }

            console.log('[Deploy] Deployment started:', response);
        } catch (error) {
            console.error('[Deploy] Start error:', error);
            showError(error.message || 'Failed to start deployment');
            setIsDeploying(false);
            setDeploymentStatus('failed');
            setDeploymentResult({ success: false, error: error.message });
            stopPolling();
        }
    };

    // ── Reset ──────────────────────────────────────────────────────────
    const handleReset = () => {
        stopPolling();
        sessionStorage.removeItem(STORAGE_KEY);
        deploymentIdRef.current = null;
        setDeploymentId(null);
        setIsDeploying(false);
        setDeploymentSteps([]);
        setDeploymentStatus(null);
        setDeploymentResult(null);
    };

    // ── Cancel Deployment ─────────────────────────────────────────────
    const handleCancel = async () => {
        const currentId = deploymentIdRef.current;
        if (!currentId) {
            // Deployment ID isn't available yet (DB record not created yet).
            // This can happen in the first few seconds after clicking Deploy.
            showError('Deployment ID not available yet — please wait a moment and try again.');
            return;
        }

        try {
            setIsCancelling(true);
            showInfo('Cancelling deployment...', 3000);

            // Call the backend cancel API — this signals the orchestrator to
            // stop at the next safe checkpoint and clean up any EC2 instances.
            await api.cancelDeployment(currentId);

            stopPolling();
            sessionStorage.removeItem(STORAGE_KEY);

            setIsDeploying(false);
            setDeploymentStatus('failed');
            setDeploymentResult({
                success: false,
                error: 'Deployment cancelled by user',
            });

            showSuccess('Deployment cancelled successfully.');

        } catch (error) {
            console.error('Cancel failed:', error);
            showError(`Failed to cancel deployment: ${error.message}`);
        } finally {
            setIsCancelling(false);
        }
    };

    // ── Render ─────────────────────────────────────────────────────────
    return (
        <div className="space-y-6 max-w-4xl">
            <ToastContainer toasts={toasts} removeToast={removeToast} />

            {/* Page Header */}
            <div>
                <div className="flex items-center gap-3 mb-2">
                    {deploymentStatus && (
                        <button
                            onClick={() => navigate('/dashboard')}
                            className="p-2 hover:bg-secondary rounded-lg transition-colors"
                        >
                            <ArrowLeft className="w-5 h-5 text-muted-foreground" />
                        </button>
                    )}
                    <h1 className="text-2xl font-bold text-foreground">Deploy Application</h1>
                </div>
                <p className="text-muted-foreground">
                    Deploy your ML application from GitHub repository to AWS EC2
                </p>
            </div>

            {/* Deployment Form */}
            {!deploymentStatus && (
                <div className="bg-card border border-border rounded-lg p-6">
                    <DeploymentForm
                        onSubmit={handleDeploy}
                        isDeploying={isDeploying}
                    />
                </div>
            )}

            {/* Progress Tracker */}
            {deploymentStatus && (
                <div className="bg-card border border-border rounded-lg p-6">
                    <ProgressTracker
                        steps={deploymentSteps}
                        status={deploymentStatus}
                        result={deploymentResult}
                    />
                    {/* Cancel button — only while in progress */}
                    {deploymentStatus === 'in_progress' && (
                        <div className="mt-4 pt-4 border-t border-border">
                            <button
                                onClick={handleCancel}
                                disabled={isCancelling}
                                className="flex items-center gap-2 px-4 py-2 text-sm text-destructive border border-destructive/40 rounded-lg hover:bg-destructive/10 transition-colors disabled:opacity-50"
                            >
                                <XCircle className="w-4 h-4" />
                                {isCancelling ? 'Cancelling...' : 'Cancel Deployment'}
                            </button>
                            <p className="text-xs text-muted-foreground mt-2">
                                Cancellation stops at the next safe checkpoint. Running EC2 instances will be cleaned up.
                            </p>
                        </div>
                    )}
                    {/* Deployment ID badge */}
                    {deploymentId && (
                        <p className="mt-4 text-xs text-muted-foreground font-mono">
                            Deployment ID: {deploymentId}
                        </p>
                    )}
                </div>
            )}

            {/* Actions after deployment */}
            {deploymentStatus && deploymentStatus !== 'in_progress' && (
                <div className="flex items-center gap-4">
                    <button
                        onClick={handleReset}
                        className="px-6 py-2.5 bg-secondary text-foreground rounded-lg hover:bg-secondary/80 transition-colors font-medium"
                    >
                        Deploy Another Application
                    </button>

                    <button
                        onClick={() => navigate('/applications')}
                        className="px-6 py-2.5 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors font-medium"
                    >
                        View All Deployments
                    </button>
                </div>
            )}

            {/* Info Card */}
            {!deploymentStatus && (
                <div className="bg-secondary/50 border border-border rounded-lg p-6">
                    <h3 className="text-sm font-semibold text-foreground mb-3">
                        📋 Deployment Requirements
                    </h3>
                    <ul className="space-y-2 text-sm text-muted-foreground">
                        <li className="flex items-start gap-2">
                            <span className="text-primary mt-0.5">•</span>
                            <span>Your GitHub repository must be <strong>public</strong> or you must provide a GitHub token</span>
                        </li>
                        <li className="flex items-start gap-2">
                            <span className="text-primary mt-0.5">•</span>
                            <span>Repository must contain a <strong>Dockerfile</strong></span>
                        </li>
                        <li className="flex items-start gap-2">
                            <span className="text-primary mt-0.5">•</span>
                            <span>Your application must listen on <strong>0.0.0.0</strong> (not 127.0.0.1)</span>
                        </li>
                        <li className="flex items-start gap-2">
                            <span className="text-primary mt-0.5">•</span>
                            <span>Ensure AWS credentials are configured in the backend</span>
                        </li>
                    </ul>
                </div>
            )}
        </div>
    );
}
