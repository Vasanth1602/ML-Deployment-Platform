import { useState } from 'react';
import { Server, Play, Square, Trash2, RefreshCw, ExternalLink } from 'lucide-react';
import ConfirmDialog from './ConfirmDialog';

export default function InstancesGrid({ instances = [], isLoading, onAction, onRefresh }) {
    const [confirmDialog, setConfirmDialog] = useState({
        isOpen: false,
        instanceId: null,
        action: null,
        instanceName: ''
    });
    const [actionInProgress, setActionInProgress] = useState(null);

    // Handle action button click
    const handleActionClick = (instanceId, action, instanceName) => {
        if (action === 'terminate') {
            // Show confirmation for terminate
            setConfirmDialog({
                isOpen: true,
                instanceId,
                action,
                instanceName
            });
        } else {
            // Execute stop/start immediately
            executeAction(instanceId, action);
        }
    };

    // Execute the action
    const executeAction = async (instanceId, action) => {
        setActionInProgress(`${instanceId}-${action}`);
        setConfirmDialog({ isOpen: false, instanceId: null, action: null, instanceName: '' });

        try {
            await onAction(instanceId, action);
        } finally {
            setActionInProgress(null);
        }
    };

    // Status indicator component
    const StatusIndicator = ({ state }) => {
        const configs = {
            running: {
                color: 'bg-green-500',
                text: 'Running',
                className: 'text-green-500'
            },
            stopped: {
                color: 'bg-gray-500',
                text: 'Stopped',
                className: 'text-gray-500'
            },
            stopping: {
                color: 'bg-yellow-500',
                text: 'Stopping',
                className: 'text-yellow-500'
            },
            pending: {
                color: 'bg-blue-500',
                text: 'Pending',
                className: 'text-blue-500'
            },
            terminated: {
                color: 'bg-red-500',
                text: 'Terminated',
                className: 'text-red-500'
            }
        };

        const config = configs[state] || configs.pending;

        return (
            <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${config.color} ${state === 'running' ? 'animate-pulse' : ''}`} />
                <span className={`text-sm font-medium ${config.className}`}>
                    {config.text}
                </span>
            </div>
        );
    };

    // Format date
    const formatDate = (dateString) => {
        if (!dateString) return 'N/A';
        const date = new Date(dateString);
        return date.toLocaleString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    };

    // Loading state
    if (isLoading) {
        return (
            <div className="bg-card border border-border rounded-lg p-12">
                <div className="flex flex-col items-center justify-center gap-4">
                    <RefreshCw className="w-8 h-8 text-primary animate-spin" />
                    <p className="text-muted-foreground">Loading instances...</p>
                </div>
            </div>
        );
    }

    // Empty state
    if (instances.length === 0) {
        return (
            <div className="bg-card border border-border rounded-lg p-12">
                <div className="flex flex-col items-center justify-center gap-4 text-center">
                    <div className="w-16 h-16 rounded-full bg-secondary flex items-center justify-center">
                        <Server className="w-8 h-8 text-muted-foreground" />
                    </div>
                    <div>
                        <h3 className="text-lg font-semibold text-foreground mb-1">No instances found</h3>
                        <p className="text-muted-foreground">
                            Deploy an application to create EC2 instances
                        </p>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <>
            <div className="space-y-4">
                {/* Header with refresh */}
                <div className="flex items-center justify-between">
                    <p className="text-sm text-muted-foreground">
                        {instances.length} instance{instances.length !== 1 ? 's' : ''} found
                    </p>

                    <button
                        onClick={onRefresh}
                        className="px-4 py-2 bg-secondary hover:bg-secondary/80 text-foreground rounded-lg transition-colors flex items-center gap-2 font-medium"
                    >
                        <RefreshCw className="w-4 h-4" />
                        Refresh
                    </button>
                </div>

                {/* Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {instances.map((instance) => {
                        const isRunning = instance.state === 'running';
                        const isStopped = instance.state === 'stopped';
                        const isTerminated = instance.state === 'terminated';
                        const instanceId = instance.instance_id;

                        return (
                            <div
                                key={instanceId}
                                className="bg-card border border-border rounded-lg p-5 hover:border-primary/50 transition-colors"
                            >
                                {/* Header */}
                                <div className="flex items-start justify-between mb-4">
                                    <div className="flex items-center gap-3">
                                        <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                                            <Server className="w-5 h-5 text-primary" />
                                        </div>
                                        <div>
                                            <h3 className="font-semibold text-foreground">
                                                {instance.name || 'Unnamed Instance'}
                                            </h3>
                                            <p className="text-xs text-muted-foreground">{instance.instance_type}</p>
                                        </div>
                                    </div>

                                    <StatusIndicator state={instance.state} />
                                </div>

                                {/* Details */}
                                <div className="space-y-2 mb-4">
                                    <div>
                                        <p className="text-xs text-muted-foreground">Instance ID</p>
                                        <code className="text-sm text-foreground bg-secondary px-2 py-0.5 rounded">
                                            {instanceId}
                                        </code>
                                    </div>

                                    {instance.public_ip && (
                                        <div>
                                            <p className="text-xs text-muted-foreground">Public IP</p>
                                            <div className="flex items-center gap-2">
                                                <code className="text-sm text-foreground">{instance.public_ip}</code>
                                                <a
                                                    href={`http://${instance.public_ip}`}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    className="text-primary hover:text-primary/80"
                                                >
                                                    <ExternalLink className="w-3.5 h-3.5" />
                                                </a>
                                            </div>
                                        </div>
                                    )}

                                    <div>
                                        <p className="text-xs text-muted-foreground">Launch Time</p>
                                        <p className="text-sm text-foreground">{formatDate(instance.launch_time)}</p>
                                    </div>
                                </div>

                                {/* Actions */}
                                {!isTerminated && (
                                    <div className="flex items-center gap-2 pt-4 border-t border-border">
                                        {/* Start button (only when stopped) */}
                                        {isStopped && (
                                            <button
                                                onClick={() => handleActionClick(instanceId, 'start', instance.name)}
                                                disabled={actionInProgress === `${instanceId}-start`}
                                                className="flex-1 px-3 py-2 bg-green-500/10 text-green-500 hover:bg-green-500/20 rounded-lg transition-colors flex items-center justify-center gap-2 font-medium text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                                            >
                                                {actionInProgress === `${instanceId}-start` ? (
                                                    <RefreshCw className="w-4 h-4 animate-spin" />
                                                ) : (
                                                    <Play className="w-4 h-4" />
                                                )}
                                                Start
                                            </button>
                                        )}

                                        {/* Stop button (only when running) */}
                                        {isRunning && (
                                            <button
                                                onClick={() => handleActionClick(instanceId, 'stop', instance.name)}
                                                disabled={actionInProgress === `${instanceId}-stop`}
                                                className="flex-1 px-3 py-2 bg-yellow-500/10 text-yellow-500 hover:bg-yellow-500/20 rounded-lg transition-colors flex items-center justify-center gap-2 font-medium text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                                            >
                                                {actionInProgress === `${instanceId}-stop` ? (
                                                    <RefreshCw className="w-4 h-4 animate-spin" />
                                                ) : (
                                                    <Square className="w-4 h-4" />
                                                )}
                                                Stop
                                            </button>
                                        )}

                                        {/* Terminate button (always available except when terminated) */}
                                        <button
                                            onClick={() => handleActionClick(instanceId, 'terminate', instance.name)}
                                            disabled={actionInProgress === `${instanceId}-terminate`}
                                            className="flex-1 px-3 py-2 bg-red-500/10 text-red-500 hover:bg-red-500/20 rounded-lg transition-colors flex items-center justify-center gap-2 font-medium text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                                        >
                                            {actionInProgress === `${instanceId}-terminate` ? (
                                                <RefreshCw className="w-4 h-4 animate-spin" />
                                            ) : (
                                                <Trash2 className="w-4 h-4" />
                                            )}
                                            Terminate
                                        </button>
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* Confirmation Dialog */}
            <ConfirmDialog
                isOpen={confirmDialog.isOpen}
                onClose={() => setConfirmDialog({ isOpen: false, instanceId: null, action: null, instanceName: '' })}
                onConfirm={() => executeAction(confirmDialog.instanceId, confirmDialog.action)}
                title="Terminate Instance?"
                message={`Are you sure you want to terminate "${confirmDialog.instanceName || confirmDialog.instanceId}"? This action cannot be undone and the instance will be permanently deleted.`}
                confirmText="Terminate"
                cancelText="Cancel"
                variant="danger"
            />
        </>
    );
}
