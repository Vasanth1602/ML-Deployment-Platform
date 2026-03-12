import { Bell, Search, LogOut, Shield, User, RefreshCw } from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useState, useRef, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../services/api';

const pageTitles = {
    '/dashboard':          'Dashboard',
    '/deploy':             'Deploy Application',
    '/applications':       'Applications',
    '/instances':          'EC2 Instances',
    '/admin/users':        'Admin — Users',
    '/admin/applications': 'Admin — Applications',
    '/admin/deployments':  'Admin — Deployments',
};

export default function Navbar() {
    const location         = useLocation();
    const navigate         = useNavigate();
    const { user, logout } = useAuth();
    const [open, setOpen]             = useState(false);
    const [refreshing, setRefreshing] = useState(false);
    const [lastRefreshed, setLastRefreshed] = useState(new Date());
    const dropdownRef = useRef(null);
    const pageTitle   = pageTitles[location.pathname] || 'Dashboard';

    // Close on outside click
    useEffect(() => {
        function handleClick(e) {
            if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
                setOpen(false);
            }
        }
        document.addEventListener('mousedown', handleClick);
        return () => document.removeEventListener('mousedown', handleClick);
    }, []);

    async function handleLogout() {
        setOpen(false);
        await logout();
        navigate('/login', { replace: true });
    }

    async function handleRefresh() {
        setRefreshing(true);
        try { await api.getMe(); } catch (_) { /* ignore */ }
        setLastRefreshed(new Date());
        setRefreshing(false);
    }

    const updatedAt = lastRefreshed.toLocaleTimeString([], {
        hour: '2-digit', minute: '2-digit', second: '2-digit',
    });

    return (
        <header className="h-16 border-b border-border bg-card relative">
            <div className="flex items-center justify-between h-full px-6">
                {/* Page Title */}
                <h2 className="text-xl font-semibold text-foreground">{pageTitle}</h2>

                {/* Right controls */}
                <div className="flex items-center gap-1">
                    <button className="p-2 text-muted-foreground hover:text-foreground hover:bg-secondary rounded-lg transition-colors">
                        <Search className="w-5 h-5" />
                    </button>

                    <button className="relative p-2 text-muted-foreground hover:text-foreground hover:bg-secondary rounded-lg transition-colors">
                        <Bell className="w-5 h-5" />
                        <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-destructive rounded-full" />
                    </button>

                    {/* Profile button + dropdown */}
                    <div ref={dropdownRef} className="relative ml-1">
                        <button
                            onClick={() => setOpen(v => !v)}
                            className="w-9 h-9 rounded-full bg-primary flex items-center justify-center text-primary-foreground hover:opacity-90 transition-opacity"
                        >
                            <User className="w-5 h-5" />
                        </button>

                        {open && (
                            <div className="absolute right-0 top-full mt-3 w-72 rounded-xl shadow-2xl z-[9999] overflow-hidden"
                                 style={{ background: 'white', border: '1px solid #e5e7eb' }}>

                                {/* ── User info ── */}
                                <div className="p-4" style={{ borderBottom: '1px solid #f3f4f6' }}>
                                    <div className="flex items-center gap-3">
                                        <div className="w-10 h-10 rounded-full flex items-center justify-center shrink-0"
                                             style={{ background: '#f3f4f6' }}>
                                            <User className="w-5 h-5" style={{ color: '#6b7280' }} />
                                        </div>
                                        <div>
                                            <p className="text-sm font-semibold truncate" style={{ color: '#111827', maxWidth: '180px' }}>
                                                {user?.email}
                                            </p>
                                            <div className="flex items-center gap-1 mt-0.5">
                                                {user?.role === 'admin' && <Shield className="w-3 h-3" style={{ color: '#3b82f6' }} />}
                                                <p className="text-xs font-medium" style={{ color: user?.role === 'admin' ? '#3b82f6' : '#6b7280', textTransform: 'capitalize' }}>
                                                    {user?.role}
                                                </p>
                                            </div>
                                            <p className="text-xs mt-0.5" style={{ color: '#9ca3af' }}>
                                                Updated {updatedAt}
                                            </p>
                                        </div>
                                    </div>
                                </div>

                                {/* ── Actions ── */}
                                <div className="p-2">
                                    <button
                                        onClick={handleRefresh}
                                        disabled={refreshing}
                                        className="flex items-center gap-2.5 w-full px-3 py-2 text-sm rounded-lg transition-colors disabled:opacity-50"
                                        style={{ color: '#374151' }}
                                        onMouseEnter={e => e.currentTarget.style.background = '#f9fafb'}
                                        onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                                    >
                                        <RefreshCw className={`w-4 h-4 shrink-0 ${refreshing ? 'animate-spin' : ''}`} />
                                        {refreshing ? 'Refreshing…' : 'Refresh profile'}
                                    </button>

                                    <div style={{ height: '1px', background: '#f3f4f6', margin: '4px 0' }} />

                                    <button
                                        onClick={handleLogout}
                                        className="flex items-center gap-2.5 w-full px-3 py-2 text-sm rounded-lg transition-colors"
                                        style={{ color: '#374151' }}
                                        onMouseEnter={e => { e.currentTarget.style.background = '#fef2f2'; e.currentTarget.style.color = '#dc2626'; }}
                                        onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = '#374151'; }}
                                    >
                                        <LogOut className="w-4 h-4 shrink-0" />
                                        Sign out
                                    </button>
                                </div>

                            </div>
                        )}
                    </div>
                </div>
            </div>
        </header>
    );
}
