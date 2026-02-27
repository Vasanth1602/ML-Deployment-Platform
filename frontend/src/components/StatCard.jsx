import { cn } from '../lib/utils';

/**
 * StatCard Component
 * Displays a metric card with icon, title, value, and optional trend
 */
export default function StatCard({
    title,
    value,
    icon: Icon,
    trend,
    trendDirection = 'up',
    className
}) {
    return (
        <div className={cn(
            "bg-card border border-border rounded-lg p-6 hover:border-primary/50 transition-colors",
            className
        )}>
            <div className="flex items-center justify-between">
                <div className="flex-1">
                    <p className="text-sm font-medium text-muted-foreground">{title}</p>
                    <p className="text-3xl font-bold text-foreground mt-2">{value}</p>

                    {trend && (
                        <p className={cn(
                            "text-xs mt-2 flex items-center gap-1",
                            trendDirection === 'up' ? 'text-green-500' : 'text-red-500'
                        )}>
                            <span>{trendDirection === 'up' ? '↑' : '↓'}</span>
                            <span>{trend}</span>
                        </p>
                    )}
                </div>

                {Icon && (
                    <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center">
                        <Icon className="w-6 h-6 text-primary" />
                    </div>
                )}
            </div>
        </div>
    );
}
