import { useEffect, useState } from 'react';
import { api } from '../../services/api';
import { Users, Mail, Shield, Clock } from 'lucide-react';

export default function AdminUsers() {
    const [users, setUsers]     = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError]     = useState('');

    useEffect(() => {
        api.request('/api/admin/users')
            .then(data => setUsers(data.users || []))
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
                    <Users className="w-5 h-5 text-primary" />
                </div>
                <div>
                    <h1 className="text-xl font-semibold text-foreground">Users</h1>
                    <p className="text-sm text-muted-foreground">{users.length} registered</p>
                </div>
            </div>

            <div className="bg-card border border-border rounded-xl overflow-hidden">
                <table className="w-full text-sm">
                    <thead className="border-b border-border bg-background/50">
                        <tr>
                            <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">Email</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">Role</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">Status</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">Joined</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                        {users.map(u => (
                            <tr key={u.id} className="hover:bg-secondary/30 transition-colors">
                                <td className="px-4 py-3 flex items-center gap-2">
                                    <Mail className="w-4 h-4 text-muted-foreground shrink-0" />
                                    <span className="text-foreground font-medium">{u.email}</span>
                                </td>
                                <td className="px-4 py-3">
                                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${
                                        u.role === 'admin'
                                            ? 'bg-primary/15 text-primary'
                                            : 'bg-secondary text-muted-foreground'
                                    }`}>
                                        {u.role === 'admin' && <Shield className="w-3 h-3" />}
                                        {u.role}
                                    </span>
                                </td>
                                <td className="px-4 py-3">
                                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                                        u.is_active
                                            ? 'bg-green-500/15 text-green-400'
                                            : 'bg-destructive/15 text-destructive'
                                    }`}>
                                        {u.is_active ? 'Active' : 'Inactive'}
                                    </span>
                                </td>
                                <td className="px-4 py-3 text-muted-foreground">
                                    <span className="flex items-center gap-1.5">
                                        <Clock className="w-3.5 h-3.5" />
                                        {u.created_at ? new Date(u.created_at).toLocaleDateString() : '—'}
                                    </span>
                                </td>
                            </tr>
                        ))}
                        {users.length === 0 && (
                            <tr><td colSpan={4} className="px-4 py-8 text-center text-muted-foreground">No users found</td></tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
