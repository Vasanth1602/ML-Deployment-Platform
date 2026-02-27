import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus } from 'lucide-react';
import ApplicationsTable from '../components/ApplicationsTable';
import { ToastContainer } from '../components/Toast';
import { useToast } from '../hooks/useToast';
import { api } from '../services/api';

export default function Applications() {
    const navigate = useNavigate();
    const { toasts, removeToast, showError } = useToast();

    const [deployments, setDeployments] = useState([]);
    const [isLoading, setIsLoading] = useState(true);

    // Fetch deployments
    const fetchDeployments = async () => {
        try {
            setIsLoading(true);
            const response = await api.getApplications();
            setDeployments(response.applications || []);
        } catch (error) {
            console.error('Failed to fetch deployments:', error);
            showError('Failed to load deployments');
        } finally {
            setIsLoading(false);
        }
    };

    // Fetch on mount
    useEffect(() => {
        fetchDeployments();
    }, []);

    return (
        <div className="space-y-6">
            {/* Toast Notifications */}
            <ToastContainer toasts={toasts} removeToast={removeToast} />

            {/* Page Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-foreground">Applications</h1>
                    <p className="text-muted-foreground mt-1">
                        View and manage your deployed applications
                    </p>
                </div>

                <button
                    onClick={() => navigate('/deploy')}
                    className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors flex items-center gap-2 font-medium"
                >
                    <Plus className="w-4 h-4" />
                    New Deployment
                </button>
            </div>

            {/* Applications Table */}
            <ApplicationsTable
                deployments={deployments}
                isLoading={isLoading}
                onRefresh={fetchDeployments}
            />
        </div>
    );
}
