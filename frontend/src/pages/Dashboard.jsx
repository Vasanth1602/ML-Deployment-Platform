import { useEffect, useState, useCallback, useRef } from 'react';
import { Package, Rocket, AlertCircle, Server, RefreshCw } from 'lucide-react';
import { Link } from 'react-router-dom';
import StatCard from '../components/StatCard';
import { api } from '../services/api';

const REFRESH_INTERVAL = 30_000; // 30 seconds

export default function Dashboard() {
    const [stats, setStats] = useState({
        total_applications: 0,
        active_deployments: 0,
        failed_deployments: 0,
        running_instances: 0,
    });
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [lastUpdated, setLastUpdated] = useState(null);
    const [refreshing, setRefreshing] = useState(false);
    const intervalRef = useRef(null);

    const loadStats = useCallback(async (isManual = false) => {
        if (isManual) setRefreshing(true);
        setError(null);
        try {
            const response = await api.getStats();
            if (response.success) {
                setStats(response.stats);
                setLastUpdated(new Date());
            }
        } catch (err) {
            console.error('Failed to load dashboard stats:', err);
            setError('Failed to load stats. Check backend connection.');
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    }, []);

    // Initial load + auto-refresh every 30s
    useEffect(() => {
        loadStats();
        intervalRef.current = setInterval(() => loadStats(), REFRESH_INTERVAL);
        return () => clearInterval(intervalRef.current);
    }, [loadStats]);

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
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-foreground">Overview</h1>
                    <p className="text-muted-foreground mt-1">
                        Monitor your deployments and infrastructure at a glance
                    </p>
                </div>
                <div className="flex items-center gap-3">
                    {lastUpdated && (
                        <span className="text-xs text-muted-foreground">
                            Updated {lastUpdated.toLocaleTimeString()}
                        </span>
                    )}
                    <button
                        onClick={() => loadStats(true)}
                        disabled={refreshing}
                        className="p-2 rounded-lg border border-border hover:bg-secondary transition-colors disabled:opacity-50"
                        title="Refresh"
                    >
                        <RefreshCw className={`w-4 h-4 text-muted-foreground ${refreshing ? 'animate-spin' : ''}`} />
                    </button>
                </div>
            </div>

            {/* Error Banner */}
            {error && (
                <div className="flex items-center gap-2 p-4 bg-destructive/10 border border-destructive/30 rounded-lg text-sm text-destructive">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    {error}
                </div>
            )}

            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                <StatCard title="Total Applications" value={stats.total_applications} icon={Package} />
                <StatCard title="Active Deployments" value={stats.active_deployments} icon={Rocket} />
                <StatCard title="Failed Deployments" value={stats.failed_deployments} icon={AlertCircle} />
                <StatCard title="Running Instances" value={stats.running_instances} icon={Server} />
            </div>

            {/* Recent Activity */}
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
                    <Link
                        to="/deploy"
                        className="flex items-center gap-3 p-4 border border-border rounded-lg hover:border-primary hover:bg-secondary/50 transition-colors"
                    >
                        <Rocket className="w-5 h-5 text-primary" />
                        <div>
                            <p className="font-medium text-foreground">New Deployment</p>
                            <p className="text-sm text-muted-foreground">Deploy from GitHub</p>
                        </div>
                    </Link>
                    <Link
                        to="/applications"
                        className="flex items-center gap-3 p-4 border border-border rounded-lg hover:border-primary hover:bg-secondary/50 transition-colors"
                    >
                        <Package className="w-5 h-5 text-primary" />
                        <div>
                            <p className="font-medium text-foreground">View Applications</p>
                            <p className="text-sm text-muted-foreground">Manage deployments</p>
                        </div>
                    </Link>
                    <Link
                        to="/instances"
                        className="flex items-center gap-3 p-4 border border-border rounded-lg hover:border-primary hover:bg-secondary/50 transition-colors"
                    >
                        <Server className="w-5 h-5 text-primary" />
                        <div>
                            <p className="font-medium text-foreground">EC2 Instances</p>
                            <p className="text-sm text-muted-foreground">Manage infrastructure</p>
                        </div>
                    </Link>
                </div>
            </div>
        </div>
    );
}
