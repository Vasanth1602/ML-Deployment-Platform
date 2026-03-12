import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { useEffect } from 'react';

import { AuthProvider } from './contexts/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Sidebar from './components/Sidebar';
import Navbar from './components/Navbar';

import Login from './pages/Login';
import Register from './pages/Register';
import Dashboard from './pages/Dashboard';
import Deploy from './pages/Deploy';
import Applications from './pages/Applications';
import Instances from './pages/Instances';
import AdminUsers from './pages/admin/AdminUsers';
import AdminDeployments from './pages/admin/AdminDeployments';
import AdminApplications from './pages/admin/AdminApplications';

import { socket } from './services/socket';
import './styles/globals.css';

/** Layout wrapper for the main app (with sidebar + navbar). */
function AppLayout() {
    useEffect(() => {
        socket.connect();
        return () => socket.disconnect();
    }, []);

    return (
        <div className="dark min-h-screen bg-background text-foreground">
            <div className="flex h-screen overflow-hidden">
                <Sidebar />
                <div className="flex flex-col flex-1 overflow-hidden">
                    <Navbar />
                    <main className="flex-1 overflow-y-auto scrollbar-thin p-6">
                        <Routes>
                            <Route index element={<Navigate to="/dashboard" replace />} />
                            <Route path="dashboard"    element={<Dashboard />} />
                            <Route path="deploy"       element={<Deploy />} />
                            <Route path="applications" element={<Applications />} />
                            <Route path="instances"    element={<Instances />} />

                            {/* Admin routes — require role="admin" */}
                            <Route element={<ProtectedRoute requiredRole="admin" />}>
                                <Route path="admin/users"        element={<AdminUsers />} />
                                <Route path="admin/applications" element={<AdminApplications />} />
                                <Route path="admin/deployments"  element={<AdminDeployments />} />
                            </Route>
                        </Routes>
                    </main>
                </div>
            </div>
        </div>
    );
}

function App() {
    return (
        <Router>
            <AuthProvider>
                <Routes>
                    {/* Public auth routes */}
                    <Route path="/login"    element={<Login />} />
                    <Route path="/register" element={<Register />} />

                    {/* All main app routes require authentication */}
                    <Route element={<ProtectedRoute />}>
                        <Route path="/*" element={<AppLayout />} />
                    </Route>
                </Routes>
            </AuthProvider>
        </Router>
    );
}

export default App;
