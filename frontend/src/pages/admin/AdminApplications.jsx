import { useEffect, useState } from 'react';
import { api } from '../../services/api';
import { Package, Mail, Globe, ExternalLink, Server } from 'lucide-react';

const STATUS_STYLES = {
    active:   'bg-green-500/15 text-green-400',
    stopped:  'bg-yellow-500/15 text-yellow-400',
    failed:   'bg-destructive/15 text-destructive',
    pending:  'bg-secondary text-muted-foreground',
    deleted:  'bg-secondary/50 text-muted-foreground line-through',
};

const DEP_STATUS_STYLES = {
    success:     'bg-green-500/15 text-green-400',
    failed:      'bg-destructive/15 text-destructive',
    in_progress: 'bg-blue-500/15 text-blue-400',
    pending:     'bg-secondary text-muted-foreground',
};

export default function AdminApplications() {
    const [apps, setApps]       = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError]     = useState('');

    useEffect(() => {
        api.request('/api/admin/applications')
            .then(data => setApps(data.applications || []))
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
                    <Package className="w-5 h-5 text-primary" />
                </div>
                <div>
                    <h1 className="text-xl font-semibold text-foreground">All Applications</h1>
                    <p className="text-sm text-muted-foreground">{apps.length} total across all users</p>
                </div>
            </div>

            <div className="bg-card border border-border rounded-xl overflow-hidden">
                <table className="w-full text-sm">
                    <thead className="border-b border-border bg-background/50">
                        <tr>
                            <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">Application</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">Owner</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">Repository</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">Instance</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">App Status</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">Last Deploy</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                        {apps.map(app => (
                            <tr key={app.id} className="hover:bg-secondary/30 transition-colors">
                                <td className="px-4 py-3">
                                    <span className="font-medium text-foreground">{app.name}</span>
                                    {app.public_ip && (
                                        <a
                                            href={`http://${app.public_ip}`}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="ml-2 inline-flex items-center gap-0.5 text-xs text-primary hover:underline"
                                        >
                                            <ExternalLink className="w-3 h-3" />
                                            {app.public_ip}
                                        </a>
                                    )}
                                </td>
                                <td className="px-4 py-3">
                                    <span className="flex items-center gap-1.5 text-muted-foreground text-xs">
                                        <Mail className="w-3.5 h-3.5 shrink-0" />
                                        {app.created_by_email || <span className="italic">unset</span>}
                                    </span>
                                </td>
                                <td className="px-4 py-3">
                                    {app.github_url ? (
                                        <a
                                            href={app.github_url}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="flex items-center gap-1.5 text-foreground hover:text-primary transition-colors"
                                        >
                                            <Globe className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                                            <span className="truncate max-w-[180px]">
                                                {app.github_url.replace('https://github.com/', '')}
                                            </span>
                                        </a>
                                    ) : (
                                        <span className="text-muted-foreground italic">—</span>
                                    )}
                                </td>
                                <td className="px-4 py-3">
                                    {app.instance_id ? (
                                        <span className="flex items-center gap-1.5 text-muted-foreground font-mono text-xs">
                                            <Server className="w-3.5 h-3.5 shrink-0" />
                                            {app.instance_id.slice(-8)}
                                        </span>
                                    ) : (
                                        <span className="text-muted-foreground italic text-xs">none</span>
                                    )}
                                </td>
                                <td className="px-4 py-3">
                                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_STYLES[app.status] || STATUS_STYLES.pending}`}>
                                        {app.status}
                                    </span>
                                </td>
                                <td className="px-4 py-3">
                                    {app.last_deployment_status ? (
                                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${DEP_STATUS_STYLES[app.last_deployment_status] || DEP_STATUS_STYLES.pending}`}>
                                            {app.last_deployment_status}
                                        </span>
                                    ) : (
                                        <span className="text-muted-foreground italic text-xs">—</span>
                                    )}
                                </td>
                            </tr>
                        ))}
                        {apps.length === 0 && (
                            <tr>
                                <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                                    No applications found
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
