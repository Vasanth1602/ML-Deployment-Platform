import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus } from 'lucide-react';
import InstancesGrid from '../components/InstancesGrid';
import { ToastContainer } from '../components/Toast';
import { useToast } from '../hooks/useToast';
import { api } from '../services/api';

export default function Instances() {
    const navigate = useNavigate();
    const { toasts, removeToast, showSuccess, showError } = useToast();

    const [instances, setInstances] = useState([]);
    const [isLoading, setIsLoading] = useState(true);

    // Fetch instances
    const fetchInstances = async () => {
        try {
            setIsLoading(true);
            const response = await api.getInstances();
            setInstances(response.instances || []);
        } catch (error) {
            console.error('Failed to fetch instances:', error);
            showError('Failed to load instances');
        } finally {
            setIsLoading(false);
        }
    };

    // Handle instance actions
    const handleAction = async (instanceId, action) => {
        try {
            if (action === 'stop') {
                await api.stopInstance(instanceId);
                showSuccess('Instance stop initiated');
            } else if (action === 'start') {
                await api.startInstance(instanceId);
                showSuccess('Instance start initiated');
            } else if (action === 'terminate') {
                await api.terminateInstance(instanceId);
                showSuccess('Instance termination initiated');
            }

            // Refresh instances after action
            setTimeout(fetchInstances, 2000);
        } catch (error) {
            console.error(`Failed to ${action} instance:`, error);
            showError(`Failed to ${action} instance: ${error.message}`);
        }
    };

    // Fetch on mount
    useEffect(() => {
        fetchInstances();
    }, []);

    return (
        <div className="space-y-6">
            {/* Toast Notifications */}
            <ToastContainer toasts={toasts} removeToast={removeToast} />

            {/* Page Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-foreground">EC2 Instances</h1>
                    <p className="text-muted-foreground mt-1">
                        Manage your AWS EC2 infrastructure
                    </p>
                </div>

                <button
                    onClick={() => navigate('/deploy')}
                    className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors flex items-center gap-2 font-medium"
                >
                    <Plus className="w-4 h-4" />
                    Deploy Application
                </button>
            </div>

            {/* Instances Grid */}
            <InstancesGrid
                instances={instances}
                isLoading={isLoading}
                onAction={handleAction}
                onRefresh={fetchInstances}
            />
        </div>
    );
}
