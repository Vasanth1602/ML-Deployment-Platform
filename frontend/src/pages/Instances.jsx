import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, RefreshCw, AlertCircle } from 'lucide-react';
import InstancesGrid from '../components/InstancesGrid';
import { ToastContainer } from '../components/Toast';
import { useToast } from '../hooks/useToast';
import { api } from '../services/api';

// Auto-refresh every 20s — EC2 state changes (pending → running) take time
const REFRESH_INTERVAL = 20_000;

export default function Instances() {
    const navigate = useNavigate();
    const { toasts, removeToast, showSuccess, showError } = useToast();

    const [instances, setInstances] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState(null);
    const [lastUpdated, setLastUpdated] = useState(null);
    const [refreshing, setRefreshing] = useState(false);
    const intervalRef = useRef(null);

    const fetchInstances = useCallback(async (isManual = false) => {
        if (isManual) setRefreshing(true);
        setError(null);
        try {
            const response = await api.getInstances();
            setInstances(response.instances || []);
            setLastUpdated(new Date());
        } catch (err) {
            console.error('Failed to fetch instances:', err);
            const msg = 'Failed to load instances. Check backend connection.';
            setError(msg);
            if (isManual) showError(msg);
        } finally {
            setIsLoading(false);
            setRefreshing(false);
        }
    }, [showError]);

    // Handle instance actions (stop / start / terminate)
    const handleAction = async (instanceId, action) => {
        try {
            if (action === 'stop') await api.stopInstance(instanceId);
            else if (action === 'start') await api.startInstance(instanceId);
            else if (action === 'terminate') await api.terminateInstance(instanceId);

            showSuccess(`Instance ${action} initiated`);

            // Refresh after 2s so the new state is visible
            setTimeout(() => fetchInstances(), 2000);
        } catch (err) {
            console.error(`Failed to ${action} instance:`, err);
            showError(`Failed to ${action} instance: ${err.message}`);
        }
    };

    // Initial load + auto-refresh every 20s
    useEffect(() => {
        fetchInstances();
        intervalRef.current = setInterval(() => fetchInstances(), REFRESH_INTERVAL);
        return () => clearInterval(intervalRef.current);
    }, [fetchInstances]);

    return (
        <div className="space-y-6">
            <ToastContainer toasts={toasts} removeToast={removeToast} />

            {/* Page Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-foreground">EC2 Instances</h1>
                    <p className="text-muted-foreground mt-1">
                        Manage your AWS EC2 infrastructure
                    </p>
                </div>

                <div className="flex items-center gap-3">
                    {lastUpdated && (
                        <span className="text-xs text-muted-foreground">
                            Updated {lastUpdated.toLocaleTimeString()}
                        </span>
                    )}
                    <button
                        onClick={() => fetchInstances(true)}
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
                        Deploy Application
                    </button>
                </div>
            </div>

            {/* Error Banner */}
            {error && (
                <div className="flex items-center gap-2 p-4 bg-destructive/10 border border-destructive/30 rounded-lg text-sm text-destructive">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    {error}
                    <button
                        onClick={() => fetchInstances(true)}
                        className="ml-auto underline hover:no-underline"
                    >
                        Retry
                    </button>
                </div>
            )}

            {/* Instances Grid */}
            <InstancesGrid
                instances={instances}
                isLoading={isLoading}
                onAction={handleAction}
                onRefresh={() => fetchInstances(true)}
            />
        </div>
    );
}
