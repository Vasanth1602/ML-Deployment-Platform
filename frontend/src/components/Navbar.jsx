import { Bell, User, Search } from 'lucide-react';
import { useLocation } from 'react-router-dom';

const pageTitles = {
    '/dashboard': 'Dashboard',
    '/deploy': 'Deploy Application',
    '/applications': 'Applications',
    '/instances': 'EC2 Instances',
};

export default function Navbar() {
    const location = useLocation();
    const pageTitle = pageTitles[location.pathname] || 'Dashboard';

    return (
        <header className="h-16 border-b border-border bg-card">
            <div className="flex items-center justify-between h-full px-6">
                {/* Page Title */}
                <div>
                    <h2 className="text-xl font-semibold text-foreground">{pageTitle}</h2>
                </div>

                {/* Right Section */}
                <div className="flex items-center gap-4">
                    {/* Search (placeholder for future) */}
                    <button className="p-2 text-muted-foreground hover:text-foreground hover:bg-secondary rounded-lg transition-colors">
                        <Search className="w-5 h-5" />
                    </button>

                    {/* Notifications */}
                    <button className="relative p-2 text-muted-foreground hover:text-foreground hover:bg-secondary rounded-lg transition-colors">
                        <Bell className="w-5 h-5" />
                        <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-destructive rounded-full"></span>
                    </button>

                    {/* User Profile */}
                    <button className="flex items-center gap-2 p-2 hover:bg-secondary rounded-lg transition-colors">
                        <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center">
                            <User className="w-4 h-4 text-primary-foreground" />
                        </div>
                    </button>
                </div>
            </div>
        </header>
    );
}
