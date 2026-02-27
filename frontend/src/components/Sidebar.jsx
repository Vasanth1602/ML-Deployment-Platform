import { NavLink } from 'react-router-dom';
import {
    LayoutDashboard,
    Rocket,
    Package,
    Server,
    Settings,
    Github
} from 'lucide-react';
import { cn } from '../lib/utils';

const navigation = [
    { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
    { name: 'Deploy', href: '/deploy', icon: Rocket },
    { name: 'Applications', href: '/applications', icon: Package },
    { name: 'Instances', href: '/instances', icon: Server },
];

export default function Sidebar() {
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
                            <h1 className="text-lg font-semibold text-foreground">DeployML</h1>
                            <p className="text-xs text-muted-foreground">Deployment Platform</p>
                        </div>
                    </div>
                </div>

                {/* Navigation */}
                <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto scrollbar-thin">
                    {navigation.map((item) => (
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
                </nav>

                {/* Footer */}
                <div className="p-4 border-t border-border">
                    <a
                        href="https://github.com"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
                    >
                        <Github className="w-4 h-4" />
                        <span>View on GitHub</span>
                    </a>
                </div>
            </div>
        </div>
    );
}
