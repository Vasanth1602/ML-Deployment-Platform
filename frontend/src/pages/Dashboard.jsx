import { useEffect, useState } from 'react';
import { Package, Rocket, AlertCircle, Server } from 'lucide-react';
import StatCard from '../components/StatCard';
import { api } from '../services/api';

export default function Dashboard() {
    const [stats, setStats] = useState({
        total_applications: 0,
        active_deployments: 0,
        failed_deployments: 0,
        running_instances: 0,
    });
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const loadStats = async () => {
            try {
                setLoading(true);

                const response = await api.getStats();

                if (response.success) {
                    setStats(response.stats);
                }
            } catch (error) {
                console.error('Failed to load dashboard stats:', error);
            } finally {
                setLoading(false);
                }
        };

        loadStats();
    }, []);

    if (loading) {
        return (
            <div className="flex items-center justify-center h-full">
                <div className="text-center">
                    <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto"></div>
                    <p className="text-muted-foreground mt-4">Loading dashboard...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Page Header */}
            <div>
                <h1 className="text-2xl font-bold text-foreground">Overview</h1>
                <p className="text-muted-foreground mt-1">
                    Monitor your deployments and infrastructure at a glance
                </p>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                <StatCard
                    title="Total Applications"
                    value={stats.total_applications}
                    icon={Package}
                />
                <StatCard
                    title="Active Deployments"
                    value={stats.active_deployments}
                    icon={Rocket}
                />
                <StatCard
                    title="Failed Deployments"
                    value={stats.failed_deployments}
                    icon={AlertCircle}
                />
                <StatCard
                    title="Running Instances"
                    value={stats.running_instances}
                    icon={Server}
                />
            </div>

            {/* Recent Activity Section */}
            <div className="bg-card border border-border rounded-lg p-6">
                <h3 className="text-lg font-semibold text-foreground mb-4">Recent Activity</h3>
                <div className="text-center py-12 text-muted-foreground">
                    <p>Activity timeline coming soon...</p>
                    <p className="text-sm mt-2">View detailed deployment history in the Applications tab</p>
                </div>
            </div>

            {/* Quick Actions */}
            <div className="bg-card border border-border rounded-lg p-6">
                <h3 className="text-lg font-semibold text-foreground mb-4">Quick Actions</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <a
                        href="/deploy"
                        className="flex items-center gap-3 p-4 border border-border rounded-lg hover:border-primary hover:bg-secondary/50 transition-colors"
                    >
                        <Rocket className="w-5 h-5 text-primary" />
                        <div>
                            <p className="font-medium text-foreground">New Deployment</p>
                            <p className="text-sm text-muted-foreground">Deploy from GitHub</p>
                        </div>
                    </a>
                    <a
                        href="/applications"
                        className="flex items-center gap-3 p-4 border border-border rounded-lg hover:border-primary hover:bg-secondary/50 transition-colors"
                    >
                        <Package className="w-5 h-5 text-primary" />
                        <div>
                            <p className="font-medium text-foreground">View Applications</p>
                            <p className="text-sm text-muted-foreground">Manage deployments</p>
                        </div>
                    </a>
                    <a
                        href="/instances"
                        className="flex items-center gap-3 p-4 border border-border rounded-lg hover:border-primary hover:bg-secondary/50 transition-colors"
                    >
                        <Server className="w-5 h-5 text-primary" />
                        <div>
                            <p className="font-medium text-foreground">EC2 Instances</p>
                            <p className="text-sm text-muted-foreground">Manage infrastructure</p>
                        </div>
                    </a>
                </div>
            </div>
        </div>
    );
}
