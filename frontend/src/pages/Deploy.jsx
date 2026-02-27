import { useState, useEffect, useCallback } from 'react';
import { ArrowLeft } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import DeploymentForm from '../components/DeploymentForm';
import ProgressTracker from '../components/ProgressTracker';
import { ToastContainer } from '../components/Toast';
import { useToast } from '../hooks/useToast';
import { api } from '../services/api';
import { socket } from '../services/socket';

export default function Deploy() {
    const navigate = useNavigate();
    const { toasts, removeToast, showSuccess, showError, showInfo } = useToast();

    const [isDeploying, setIsDeploying] = useState(false);
    const [deploymentSteps, setDeploymentSteps] = useState([]);
    const [deploymentStatus, setDeploymentStatus] = useState(null);
    const [deploymentResult, setDeploymentResult] = useState(null);

    // Handle deployment progress updates via WebSocket
    const handleDeploymentProgress = useCallback((data) => {
        console.log('📡 Deployment progress:', data);

        setDeploymentSteps(prev => {
            // Check if step already exists
            const existingIndex = prev.findIndex(s => s.step === data.step);

            if (existingIndex >= 0) {
                // Update existing step
                const updated = [...prev];
                updated[existingIndex] = {
                    step: data.step,
                    message: data.message,
                    status: data.status,
                };
                return updated;
            } else {
                // Add new step
                return [
                    ...prev,
                    {
                        step: data.step,
                        message: data.message,
                        status: data.status,
                    }
                ];
            }
        });
    }, []);

    // Handle deployment completion via WebSocket
    const handleDeploymentComplete = useCallback((data) => {
        console.log('✅ Deployment complete:', data);

        setIsDeploying(false);
        setDeploymentStatus(data.success ? 'success' : 'failed');
        setDeploymentResult(data);

        if (data.success) {
            showSuccess('Deployment completed successfully! 🎉', 7000);
        } else {
            showError(`Deployment failed: ${data.error || 'Unknown error'}`, 7000);
        }
    }, [showSuccess, showError]);

    // Setup WebSocket listeners
    useEffect(() => {
        // Explicitly connect socket
        console.log('🔌 Setting up WebSocket listeners...');
        socket.connect();

        // Add debug logging for all events
        const socketInstance = socket.getSocket();
        if (socketInstance) {
            socketInstance.onAny((eventName, ...args) => {
                console.log(`📡 WebSocket event received: ${eventName}`, args);
            });
        }

        socket.onDeploymentProgress(handleDeploymentProgress);
        socket.onDeploymentComplete(handleDeploymentComplete);

        console.log('✅ WebSocket listeners attached');

        return () => {
            console.log('🔌 Cleaning up WebSocket listeners...');
            socket.offDeploymentProgress(handleDeploymentProgress);
            socket.offDeploymentComplete(handleDeploymentComplete);
        };
    }, [handleDeploymentProgress, handleDeploymentComplete]);

    // Handle form submission
    const handleDeploy = async (formData) => {
        try {
            // Ensure WebSocket is connected
            if (!socket.isConnected()) {
                console.log('⏳ WebSocket not connected, connecting...');
                socket.connect();
                // Wait a bit for connection
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

            console.log('Deployment started:', response);
        } catch (error) {
            console.error('Deployment error:', error);
            showError(error.message || 'Failed to start deployment');
            setIsDeploying(false);
            setDeploymentStatus('failed');
            setDeploymentResult({
                success: false,
                error: error.message
            });
        }
    };

    // Reset deployment
    const handleReset = () => {
        setIsDeploying(false);
        setDeploymentSteps([]);
        setDeploymentStatus(null);
        setDeploymentResult(null);
    };

    return (
        <div className="space-y-6 max-w-4xl">
            {/* Toast Notifications */}
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
                </div>
            )}

            {/* Actions after deployment */}
            {deploymentStatus && (
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
