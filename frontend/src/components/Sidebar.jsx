import { NavLink } from 'react-router-dom';
import {
    LayoutDashboard,
    Rocket,
    Package,
    Server,
    Settings,
    Shield,
    Users,
} from 'lucide-react';
import { cn } from '../lib/utils';
import { useAuth } from '../contexts/AuthContext';

const mainNav = [
    { name: 'Dashboard',    href: '/dashboard',    icon: LayoutDashboard },
    { name: 'Deploy',       href: '/deploy',       icon: Rocket },
    { name: 'Applications', href: '/applications', icon: Package },
    { name: 'Instances',    href: '/instances',    icon: Server },
];

const adminNav = [
    { name: 'Admin: Users',        href: '/admin/users',        icon: Users },
    { name: 'Admin: Applications', href: '/admin/applications', icon: Package },
    { name: 'Admin: Deployments',  href: '/admin/deployments',  icon: Settings },
];

export default function Sidebar() {
    const { user } = useAuth();
    const isAdmin  = user?.role === 'admin';

    return (
        <div className="hidden md:flex md:flex-shrink-0">
            <div className="flex flex-col w-64 border-r border-border bg-card">
                {/* Logo */}
                <div className="flex items-center h-16 px-6 border-b border-border">
                    <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
                            <Rocket className="w-5 h-5 text-primary-foreground" />
                        </div>
                        <div>
                            <h1 className="text-base font-semibold text-foreground leading-tight">ML Deployment</h1>
                            <p className="text-xs text-muted-foreground">Platform</p>
                        </div>
                    </div>
                </div>

                {/* Main Navigation */}
                <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto scrollbar-thin">
                    {mainNav.map((item) => (
                        <NavLink
                            key={item.name}
                            to={item.href}
                            className={({ isActive }) =>
                                cn(
                                    'flex items-center gap-3 px-3 py-2.5 text-sm font-medium rounded-lg transition-colors',
                                    isActive
                                        ? 'bg-secondary text-foreground'
                                        : 'text-muted-foreground hover:bg-secondary/50 hover:text-foreground'
                                )
                            }
                        >
                            <item.icon className="w-5 h-5" />
                            {item.name}
                        </NavLink>
                    ))}

                    {/* Admin section — only visible to admins */}
                    {isAdmin && (
                        <>
                            <div className="pt-4 pb-1 px-3">
                                <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                                    <Shield className="w-3.5 h-3.5" />
                                    Admin
                                </div>
                            </div>
                            {adminNav.map((item) => (
                                <NavLink
                                    key={item.name}
                                    to={item.href}
                                    className={({ isActive }) =>
                                        cn(
                                            'flex items-center gap-3 px-3 py-2.5 text-sm font-medium rounded-lg transition-colors',
                                            isActive
                                                ? 'bg-secondary text-foreground'
                                                : 'text-muted-foreground hover:bg-secondary/50 hover:text-foreground'
                                        )
                                    }
                                >
                                    <item.icon className="w-5 h-5" />
                                    {item.name}
                                </NavLink>
                            ))}
                        </>
                    )}
                </nav>
            </div>
        </div>
    );
}
