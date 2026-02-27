import { CheckCircle2, Circle, XCircle, Loader2, ExternalLink } from 'lucide-react';
import { cn } from '../lib/utils';
import { DEPLOYMENT_STEPS } from '../utils/constants';

/**
 * ProgressTracker Component
 * Displays real-time deployment progress with step-by-step visualization
 */
export default function ProgressTracker({
    steps = [],
    currentStep,
    status,
    result
}) {
    // Calculate progress percentage
    const completedSteps = steps.filter(s => s.status === 'success').length;
    const progress = (completedSteps / DEPLOYMENT_STEPS.length) * 100;

    const getStepIcon = (step) => {
        if (step.status === 'success') {
            return <CheckCircle2 className="w-5 h-5 text-green-500" />;
        } else if (step.status === 'error') {
            return <XCircle className="w-5 h-5 text-destructive" />;
        } else if (step.status === 'in_progress') {
            return <Loader2 className="w-5 h-5 text-primary animate-spin" />;
        } else {
            return <Circle className="w-5 h-5 text-muted-foreground" />;
        }
    };

    const getStatusBadge = () => {
        if (status === 'success') {
            return (
                <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-green-500/10 text-green-500 text-sm font-medium">
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Deployment Successful</span>
                </div>
            );
        } else if (status === 'failed') {
            return (
                <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-destructive/10 text-destructive text-sm font-medium">
                    <XCircle className="w-4 h-4" />
                    <span>Deployment Failed</span>
                </div>
            );
        } else {
            return (
                <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-primary/10 text-primary text-sm font-medium">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Deploying...</span>
                </div>
            );
        }
    };

    return (
        <div className="space-y-6">
            {/* Status Badge */}
            <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold text-foreground">Deployment Progress</h3>
                {getStatusBadge()}
            </div>

            {/* Progress Bar */}
            <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Progress</span>
                    <span className="font-medium text-foreground">{Math.round(progress)}%</span>
                </div>
                <div className="w-full h-2 bg-secondary rounded-full overflow-hidden">
                    <div
                        className={cn(
                            "h-full transition-all duration-500 ease-out",
                            status === 'success' ? 'bg-green-500' :
                                status === 'failed' ? 'bg-destructive' :
                                    'bg-primary'
                        )}
                        style={{ width: `${progress}%` }}
                    />
                </div>
            </div>

            {/* Deployment Steps */}
            <div className="space-y-3">
                {steps.length === 0 ? (
                    <div className="text-center py-8 text-muted-foreground">
                        <Loader2 className="w-8 h-8 animate-spin mx-auto mb-2" />
                        <p>Initializing deployment...</p>
                    </div>
                ) : (
                    steps.map((step, index) => (
                        <div
                            key={index}
                            className={cn(
                                "flex items-start gap-3 p-4 rounded-lg border transition-colors",
                                step.status === 'success' ? 'bg-green-500/5 border-green-500/20' :
                                    step.status === 'error' ? 'bg-destructive/5 border-destructive/20' :
                                        step.status === 'in_progress' ? 'bg-primary/5 border-primary/20' :
                                            'bg-secondary border-border'
                            )}
                        >
                            {/* Icon */}
                            <div className="flex-shrink-0 mt-0.5">
                                {getStepIcon(step)}
                            </div>

                            {/* Content */}
                            <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2">
                                    <h4 className="text-sm font-medium text-foreground">
                                        {step.step}
                                    </h4>
                                    {step.status === 'in_progress' && (
                                        <span className="text-xs text-muted-foreground">(in progress)</span>
                                    )}
                                </div>
                                {step.message && (
                                    <p className="mt-1 text-sm text-muted-foreground">
                                        {step.message}
                                    </p>
                                )}
                            </div>
                        </div>
                    ))
                )}
            </div>

            {/* Deployment Result */}
            {result && (
                <div className={cn(
                    "p-6 rounded-lg border",
                    result.success
                        ? "bg-green-500/5 border-green-500/20"
                        : "bg-destructive/5 border-destructive/20"
                )}>
                    {result.success ? (
                        <div className="space-y-4">
                            <div className="flex items-center gap-3">
                                <CheckCircle2 className="w-6 h-6 text-green-500" />
                                <h3 className="text-lg font-semibold text-foreground">
                                    Deployment Successful! 🎉
                                </h3>
                            </div>

                            <div className="space-y-2">
                                <div className="flex items-center justify-between py-2 border-b border-border">
                                    <span className="text-sm text-muted-foreground">Application URL:</span>
                                    <a
                                        href={result.url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="flex items-center gap-2 text-sm font-medium text-primary hover:underline"
                                    >
                                        {result.url}
                                        <ExternalLink className="w-4 h-4" />
                                    </a>
                                </div>

                                {result.instance_id && (
                                    <div className="flex items-center justify-between py-2 border-b border-border">
                                        <span className="text-sm text-muted-foreground">Instance ID:</span>
                                        <code className="text-sm font-mono text-foreground">
                                            {result.instance_id}
                                        </code>
                                    </div>
                                )}

                                {result.container_name && (
                                    <div className="flex items-center justify-between py-2">
                                        <span className="text-sm text-muted-foreground">Container:</span>
                                        <code className="text-sm font-mono text-foreground">
                                            {result.container_name}
                                        </code>
                                    </div>
                                )}
                            </div>
                        </div>
                    ) : (
                        <div className="space-y-3">
                            <div className="flex items-center gap-3">
                                <XCircle className="w-6 h-6 text-destructive" />
                                <h3 className="text-lg font-semibold text-foreground">
                                    Deployment Failed
                                </h3>
                            </div>

                            <p className="text-sm text-muted-foreground">
                                {result.error || 'An unknown error occurred during deployment.'}
                            </p>

                            <div className="mt-4 p-3 bg-secondary rounded-lg">
                                <p className="text-xs text-muted-foreground">
                                    💡 <strong>Tip:</strong> Check the deployment logs for more details or try deploying again.
                                </p>
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
