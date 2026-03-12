import { useEffect, useState } from 'react';
import { api } from '../../services/api';
import { Settings, GitBranch, Clock, Mail } from 'lucide-react';

const STATUS_STYLES = {
    success:     'bg-green-500/15 text-green-400',
    failed:      'bg-destructive/15 text-destructive',
    in_progress: 'bg-blue-500/15 text-blue-400',
    cancelled:   'bg-yellow-500/15 text-yellow-400',
    pending:     'bg-secondary text-muted-foreground',
};

export default function AdminDeployments() {
    const [deployments, setDeployments] = useState([]);
    const [loading, setLoading]         = useState(true);
    const [error, setError]             = useState('');

    useEffect(() => {
        api.request('/api/admin/deployments')
            .then(data => setDeployments(data.deployments || []))
            .catch(err => setError(err.message))
            .finally(() => setLoading(false));
    }, []);

    if (loading) return (
        <div className="flex items-center justify-center h-48">
            <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
        </div>
    );

    if (error) return (
        <div className="p-4 rounded-lg bg-destructive/10 text-destructive text-sm">{error}</div>
    );

    return (
        <div className="space-y-6">
            <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
                    <Settings className="w-5 h-5 text-primary" />
                </div>
                <div>
                    <h1 className="text-xl font-semibold text-foreground">All Deployments</h1>
                    <p className="text-sm text-muted-foreground">{deployments.length} total</p>
                </div>
            </div>

            <div className="bg-card border border-border rounded-xl overflow-hidden">
                <table className="w-full text-sm">
                    <thead className="border-b border-border bg-background/50">
                        <tr>
                            <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">ID</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">Repository</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">Owner</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">Status</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">Started</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">Duration</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                        {deployments.map(d => (
                            <tr key={d.id} className="hover:bg-secondary/30 transition-colors">
                                <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                                    {d.short_id || d.id?.slice(0, 8)}
                                </td>
                                <td className="px-4 py-3">
                                    <span className="flex items-center gap-1.5 text-foreground">
                                        <GitBranch className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                                        {d.github_url
                                            ? d.github_url.replace('https://github.com/', '')
                                            : <span className="text-muted-foreground italic">unknown</span>}
                                    </span>
                                </td>
                                <td className="px-4 py-3">
                                    <span className="flex items-center gap-1.5 text-muted-foreground text-xs">
                                        <Mail className="w-3.5 h-3.5 shrink-0" />
                                        {d.triggered_by_email || <span className="italic">unset</span>}
                                    </span>
                                </td>
                                <td className="px-4 py-3">
                                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_STYLES[d.status] || STATUS_STYLES.pending}`}>
                                        {d.status}
                                    </span>
                                </td>
                                <td className="px-4 py-3 text-muted-foreground">
                                    <span className="flex items-center gap-1.5">
                                        <Clock className="w-3.5 h-3.5" />
                                        {d.started_at ? new Date(d.started_at).toLocaleString() : '—'}
                                    </span>
                                </td>
                                <td className="px-4 py-3 text-muted-foreground">
                                    {d.duration_seconds != null
                                        ? `${Math.round(d.duration_seconds)}s`
                                        : '—'}
                                </td>
                            </tr>
                        ))}
                        {deployments.length === 0 && (
                            <tr><td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">No deployments found</td></tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}