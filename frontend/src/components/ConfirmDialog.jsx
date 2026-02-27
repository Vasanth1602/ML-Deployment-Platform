import { useEffect } from 'react';
import { X, AlertTriangle } from 'lucide-react';

export default function ConfirmDialog({
    isOpen,
    onClose,
    onConfirm,
    title,
    message,
    confirmText = 'Confirm',
    cancelText = 'Cancel',
    variant = 'default' // 'default' or 'danger'
}) {
    // Handle keyboard events
    useEffect(() => {
        if (!isOpen) return;

        const handleKeyDown = (e) => {
            if (e.key === 'Escape') {
                onClose();
            } else if (e.key === 'Enter') {
                onConfirm();
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [isOpen, onClose, onConfirm]);

    if (!isOpen) return null;

    const isDanger = variant === 'danger';

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
            {/* Backdrop */}
            <div
                className="absolute inset-0 bg-black/50 backdrop-blur-sm"
                onClick={onClose}
            />

            {/* Dialog */}
            <div className="relative bg-card border border-border rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
                {/* Close button */}
                <button
                    onClick={onClose}
                    className="absolute top-4 right-4 p-1 hover:bg-secondary rounded-lg transition-colors"
                >
                    <X className="w-5 h-5 text-muted-foreground" />
                </button>

                {/* Icon */}
                {isDanger && (
                    <div className="mb-4">
                        <div className="w-12 h-12 rounded-full bg-red-500/10 flex items-center justify-center">
                            <AlertTriangle className="w-6 h-6 text-red-500" />
                        </div>
                    </div>
                )}

                {/* Title */}
                <h2 className="text-xl font-bold text-foreground mb-2">
                    {title}
                </h2>

                {/* Message */}
                <p className="text-muted-foreground mb-6">
                    {message}
                </p>

                {/* Actions */}
                <div className="flex items-center gap-3 justify-end">
                    <button
                        onClick={onClose}
                        className="px-4 py-2 bg-secondary text-foreground rounded-lg hover:bg-secondary/80 transition-colors font-medium"
                    >
                        {cancelText}
                    </button>

                    <button
                        onClick={onConfirm}
                        className={`px-4 py-2 rounded-lg font-medium transition-colors ${isDanger
                                ? 'bg-red-500 text-white hover:bg-red-600'
                                : 'bg-primary text-primary-foreground hover:bg-primary/90'
                            }`}
                    >
                        {confirmText}
                    </button>
                </div>
            </div>
        </div>
    );
}
