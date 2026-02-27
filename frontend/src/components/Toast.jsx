import { useEffect } from 'react';
import { CheckCircle2, XCircle, Info, AlertTriangle, X } from 'lucide-react';
import { cn } from '../lib/utils';

/**
 * Toast Component
 * Notification toast for user feedback
 */
export default function Toast({ message, type = 'info', onClose, duration = 5000 }) {
    useEffect(() => {
        if (duration > 0) {
            const timer = setTimeout(() => {
                onClose();
            }, duration);

            return () => clearTimeout(timer);
        }
    }, [duration, onClose]);

    const getIcon = () => {
        switch (type) {
            case 'success':
                return <CheckCircle2 className="w-5 h-5 text-green-500" />;
            case 'error':
                return <XCircle className="w-5 h-5 text-destructive" />;
            case 'warning':
                return <AlertTriangle className="w-5 h-5 text-yellow-500" />;
            default:
                return <Info className="w-5 h-5 text-primary" />;
        }
    };

    const getStyles = () => {
        switch (type) {
            case 'success':
                return 'bg-green-500/10 border-green-500/20 text-green-500';
            case 'error':
                return 'bg-destructive/10 border-destructive/20 text-destructive';
            case 'warning':
                return 'bg-yellow-500/10 border-yellow-500/20 text-yellow-500';
            default:
                return 'bg-primary/10 border-primary/20 text-primary';
        }
    };

    return (
        <div
            className={cn(
                "flex items-center gap-3 p-4 rounded-lg border shadow-lg",
                "animate-in slide-in-from-right-full duration-300",
                getStyles()
            )}
        >
            {/* Icon */}
            <div className="flex-shrink-0">
                {getIcon()}
            </div>

            {/* Message */}
            <p className="flex-1 text-sm font-medium text-foreground">
                {message}
            </p>

            {/* Close Button */}
            <button
                onClick={onClose}
                className="flex-shrink-0 p-1 hover:bg-secondary rounded transition-colors"
            >
                <X className="w-4 h-4 text-muted-foreground" />
            </button>
        </div>
    );
}

/**
 * ToastContainer Component
 * Container for managing multiple toasts
 */
export function ToastContainer({ toasts, removeToast }) {
    return (
        <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 max-w-md">
            {toasts.map((toast) => (
                <Toast
                    key={toast.id}
                    message={toast.message}
                    type={toast.type}
                    duration={toast.duration}
                    onClose={() => removeToast(toast.id)}
                />
            ))}
        </div>
    );
}
