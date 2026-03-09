import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, RefreshCw, AlertCircle } from 'lucide-react';
import ApplicationsTable from '../components/ApplicationsTable';
import { ToastContainer } from '../components/Toast';
import { useToast } from '../hooks/useToast';
import { api } from '../services/api';

// Auto-refresh every 15s — useful when a deployment is in_progress
const REFRESH_INTERVAL = 15_000;

export default function Applications() {
    const navigate = useNavigate();
    const { toasts, removeToast, showError } = useToast();

    const [deployments, setDeployments] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState(null);
    const [lastUpdated, setLastUpdated] = useState(null);
    const [refreshing, setRefreshing] = useState(false);
    const intervalRef = useRef(null);

    const fetchDeployments = useCallback(async (isManual = false) => {
        if (isManual) setRefreshing(true);
        setError(null);
        try {
            const response = await api.getApplications();
            setDeployments(response.applications || []);
            setLastUpdated(new Date());
        } catch (err) {
            console.error('Failed to fetch deployments:', err);
            const msg = 'Failed to load deployments. Check backend connection.';
            setError(msg);
            if (isManual) showError(msg);
        } finally {
            setIsLoading(false);
            setRefreshing(false);
        }
    }, [showError]);

    // Initial load + auto-refresh every 15s (catches in-progress state changes)
    useEffect(() => {
        fetchDeployments();
        intervalRef.current = setInterval(() => fetchDeployments(), REFRESH_INTERVAL);
        return () => clearInterval(intervalRef.current);
    }, [fetchDeployments]);

    return (
        <div className="space-y-6">
            <ToastContainer toasts={toasts} removeToast={removeToast} />

            {/* Page Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-foreground">Applications</h1>
                    <p className="text-muted-foreground mt-1">
                        View and manage your deployed applications
                    </p>
                </div>

                <div className="flex items-center gap-3">
                    {lastUpdated && (
                        <span className="text-xs text-muted-foreground">
                            Updated {lastUpdated.toLocaleTimeString()}
                        </span>
                    )}
                    <button
                        onClick={() => fetchDeployments(true)}
                        disabled={refreshing}
                        className="p-2 rounded-lg border border-border hover:bg-secondary transition-colors disabled:opacity-50"
                        title="Refresh"
                    >
                        <RefreshCw className={`w-4 h-4 text-muted-foreground ${refreshing ? 'animate-spin' : ''}`} />
                    </button>
                    <button
                        onClick={() => navigate('/deploy')}
                        className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors flex items-center gap-2 font-medium"
                    >
                        <Plus className="w-4 h-4" />
                        New Deployment
                    </button>
                </div>
            </div>

            {/* Error Banner */}
            {error && (
                <div className="flex items-center gap-2 p-4 bg-destructive/10 border border-destructive/30 rounded-lg text-sm text-destructive">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    {error}
                    <button
                        onClick={() => fetchDeployments(true)}
                        className="ml-auto underline hover:no-underline"
                    >
                        Retry
                    </button>
                </div>
            )}

            {/* Applications Table */}
            <ApplicationsTable
                deployments={deployments}
                isLoading={isLoading}
                onRefresh={() => fetchDeployments(true)}
            />
        </div>
    );
}
