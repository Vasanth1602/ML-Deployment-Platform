/**
 * ProtectedRoute.jsx
 * Wraps routes that require authentication and/or a specific role.
 *
 * Usage:
 *   <ProtectedRoute />                     — requires authentication only
 *   <ProtectedRoute requiredRole="admin" /> — requires admin role
 */

import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export default function ProtectedRoute({ requiredRole }) {
    const { isAuthenticated, isLoading, user } = useAuth();

    // Still rehydrating token — don't redirect yet
    if (isLoading) {
        return (
            <div className="flex items-center justify-center h-screen bg-background">
                <div className="flex flex-col items-center gap-3">
                    <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                    <p className="text-sm text-muted-foreground">Loading…</p>
                </div>
            </div>
        );
    }

    // Not authenticated → redirect to login
    if (!isAuthenticated) {
        return <Navigate to="/login" replace />;
    }

    // Authenticated but wrong role → redirect to dashboard
    if (requiredRole && user?.role !== requiredRole) {
        return <Navigate to="/dashboard" replace />;
    }

    return <Outlet />;
}
