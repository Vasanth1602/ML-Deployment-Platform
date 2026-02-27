import { useState } from 'react';
import { ExternalLink, RefreshCw, Search, CheckCircle, XCircle, Clock } from 'lucide-react';

export default function ApplicationsTable({ deployments = [], isLoading, onRefresh }) {
    const [searchTerm, setSearchTerm] = useState('');

    // Filter deployments by search term
    const filteredDeployments = deployments.filter(app => {
        const searchLower = searchTerm.toLowerCase();
        return (
            app.name?.toLowerCase().includes(searchLower) ||
            app.github_url?.toLowerCase().includes(searchLower) ||
            app.instance_id?.toLowerCase().includes(searchLower)
        );
});

    // Status badge component
    const StatusBadge = ({ status }) => {
        const configs = {
            success: {
                icon: CheckCircle,
                text: 'Success',
                className: 'bg-green-500/10 text-green-500 border-green-500/20'
            },
            failed: {
                icon: XCircle,
                text: 'Failed',
                className: 'bg-red-500/10 text-red-500 border-red-500/20'
            },
            in_progress: {
                icon: Clock,
                text: 'In Progress',
                className: 'bg-blue-500/10 text-blue-500 border-blue-500/20'
            }
        };

        const config = configs[status] || configs.in_progress;
        const Icon = config.icon;

        return (
            <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${config.className}`}>
                <Icon className="w-3.5 h-3.5" />
                {config.text}
            </span>
        );
    };

    // Format date
    const formatDate = (dateString) => {
        if (!dateString) return 'N/A';
        const date = new Date(dateString);
        return date.toLocaleString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    };

    // Loading state
    if (isLoading) {
        return (
            <div className="bg-card border border-border rounded-lg p-12">
                <div className="flex flex-col items-center justify-center gap-4">
                    <RefreshCw className="w-8 h-8 text-primary animate-spin" />
                    <p className="text-muted-foreground">Loading deployments...</p>
                </div>
            </div>
        );
    }

    // Empty state
    if (deployments.length === 0) {
        return (
            <div className="bg-card border border-border rounded-lg p-12">
                <div className="flex flex-col items-center justify-center gap-4 text-center">
                    <div className="w-16 h-16 rounded-full bg-secondary flex items-center justify-center">
                        <ExternalLink className="w-8 h-8 text-muted-foreground" />
                    </div>
                    <div>
                        <h3 className="text-lg font-semibold text-foreground mb-1">No deployments yet</h3>
                        <p className="text-muted-foreground">
                            Deploy your first application to see it here
                        </p>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-4">
            {/* Header with search and refresh */}
            <div className="flex items-center gap-4">
                {/* Search */}
                <div className="flex-1 relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                    <input
                        type="text"
                        placeholder="Search by name, URL, or instance ID..."
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        className="w-full pl-10 pr-4 py-2 bg-secondary border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                </div>

                {/* Refresh button */}
                <button
                    onClick={onRefresh}
                    className="px-4 py-2 bg-secondary hover:bg-secondary/80 text-foreground rounded-lg transition-colors flex items-center gap-2 font-medium"
                >
                    <RefreshCw className="w-4 h-4" />
                    Refresh
                </button>
            </div>

            {/* Table */}
            <div className="bg-card border border-border rounded-lg overflow-hidden">
                <div className="overflow-x-auto">
                    <table className="w-full">
                        <thead>
                            <tr className="border-b border-border bg-secondary/50">
                                <th className="text-left px-6 py-3 text-sm font-semibold text-foreground">
                                    Application Name
                                </th>
                                <th className="text-left px-6 py-3 text-sm font-semibold text-foreground">
                                    GitHub URL
                                </th>
                                <th className="text-left px-6 py-3 text-sm font-semibold text-foreground">
                                    Status
                                </th>
                                <th className="text-left px-6 py-3 text-sm font-semibold text-foreground">
                                    Instance ID
                                </th>
                                <th className="text-left px-6 py-3 text-sm font-semibold text-foreground">
                                    Application URL
                                </th>
                                <th className="text-left px-6 py-3 text-sm font-semibold text-foreground">
                                    Created At
                                </th>
                            </tr>
                        </thead>
                        <tbody>
                            {filteredDeployments.length === 0 ? (
                                <tr>
                                    <td colSpan="6" className="px-6 py-12 text-center text-muted-foreground">
                                        No deployments match your search
                                    </td>
                                </tr>
                            ) : (
                                filteredDeployments.map((app) => (
                                    <tr
                                        key={app.id}
                                        className="border-b border-border last:border-0 hover:bg-secondary/30 transition-colors"
                                    >
                                        {/* Application Name */}
                                        <td className="px-6 py-4">
                                            <span className="font-medium text-foreground">
                                                {app.name}
                                            </span>
                                        </td>

                                        {/* GitHub URL */}
                                        <td className="px-6 py-4">
                                            <a
                                                href={app.github_url}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="text-primary hover:underline flex items-center gap-1 max-w-xs truncate"
                                            >
                                                <span className="truncate">{app.github_url}</span>
                                                <ExternalLink className="w-3.5 h-3.5 flex-shrink-0" />
                                            </a>
                                        </td>

                                        {/* Status */}
                                        <td className="px-6 py-4">
                                            <StatusBadge status={app.deployment_status} />
                                        </td>

                                        {/* Instance ID */}
                                        <td className="px-6 py-4">
                                            <code className="text-sm text-muted-foreground bg-secondary px-2 py-1 rounded">
                                                {app.instance_id || 'N/A'}
                                            </code>
                                        </td>

                                        {/* Application URL */}
                                        <td className="px-6 py-4">
                                            {app.deployment_url ? (
                                                <a
                                                    href={app.deployment_url}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    className="text-primary hover:underline flex items-center gap-1"
                                                >
                                                    <span>View App</span>
                                                    <ExternalLink className="w-3.5 h-3.5" />
                                                </a>
                                            ) : (
                                                <span className="text-muted-foreground">N/A</span>
                                            )}
                                        </td>

                                        {/* Created At */}
                                        <td className="px-6 py-4 text-sm text-muted-foreground whitespace-nowrap">
                                            {formatDate(app.created_at)}
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Results count */}
            <div className="text-sm text-muted-foreground">
                Showing {filteredDeployments.length} of {deployments.length} application{deployments.length !== 1 ? 's' : ''}
            </div>
        </div>
    );
}
