/**
 * AuthContext.jsx
 * Manages authentication state globally: token, user, isAuthenticated.
 *
 * Design decision — localStorage:
 *   Tokens are stored in localStorage for simplicity (internal tool).
 *   Production tradeoff: httpOnly cookies would be more XSS-resistant,
 *   but require server-side cookie handling + CSRF protection.
 *   Accepted for this stage; revisit before public-facing deployment.
 */

import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { api } from '../services/api';

const AuthContext = createContext(null);

const TOKEN_KEY = 'ml_deploy_token';

export function AuthProvider({ children }) {
    const [token, setToken]               = useState(() => localStorage.getItem(TOKEN_KEY));
    const [user, setUser]                 = useState(null);
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const [isLoading, setIsLoading]       = useState(true);  // true while rehydrating

    // ── Persist token to localStorage whenever it changes ──────────────────
    const saveToken = useCallback((newToken) => {
        if (newToken) {
            localStorage.setItem(TOKEN_KEY, newToken);
        } else {
            localStorage.removeItem(TOKEN_KEY);
        }
        setToken(newToken);
    }, []);

    // ── On mount: rehydrate state by calling GET /api/auth/me ───────────────
    // This ensures that a page refresh keeps the user logged in
    // as long as the token is still valid (not expired).
    useEffect(() => {
        const storedToken = localStorage.getItem(TOKEN_KEY);
        if (!storedToken) {
            setIsLoading(false);
            return;
        }

        api.getMe()
            .then((data) => {
                setUser(data.user);
                setIsAuthenticated(true);
            })
            .catch(() => {
                // Token expired or invalid — clear it
                localStorage.removeItem(TOKEN_KEY);
                setToken(null);
                setUser(null);
                setIsAuthenticated(false);
            })
            .finally(() => {
                setIsLoading(false);
            });
    }, []);

    // ── Login ───────────────────────────────────────────────────────────────
    const login = useCallback(async (email, password) => {
        const data = await api.login({ email, password });
        saveToken(data.token);
        setUser(data.user);
        setIsAuthenticated(true);
        return data.user;
    }, [saveToken]);

    // ── Register ─────────────────────────────────────────────────────────────
    const register = useCallback(async (email, password) => {
        const data = await api.register({ email, password });
        saveToken(data.token);
        setUser(data.user);
        setIsAuthenticated(true);
        return data.user;
    }, [saveToken]);

    // ── Logout ───────────────────────────────────────────────────────────────
    const logout = useCallback(async () => {
        try {
            await api.logout();
        } catch {
            // Even if the server call fails, clear client state
        }
        saveToken(null);
        setUser(null);
        setIsAuthenticated(false);
    }, [saveToken]);

    const value = {
        token,
        user,
        isAuthenticated,
        isLoading,
        login,
        register,
        logout,
    };

    return (
        <AuthContext.Provider value={value}>
            {children}
        </AuthContext.Provider>
    );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
    const ctx = useContext(AuthContext);
    if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
    return ctx;
}
