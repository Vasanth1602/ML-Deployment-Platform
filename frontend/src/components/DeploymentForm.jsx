import { useState } from 'react';
import { Rocket, Github, Server, Plug } from 'lucide-react';
import { cn } from '../lib/utils';

/**
 * DeploymentForm Component
 * Form for deploying applications from GitHub repositories
 */
export default function DeploymentForm({ onSubmit, isDeploying }) {
    const [formData, setFormData] = useState({
        github_url: '',
        instance_name: '',
        container_port: '8000',
        host_port: '8000',
    });

    const [errors, setErrors] = useState({});

    const validateGithubUrl = (url) => {
        if (!url) return 'GitHub URL is required';

        const githubPattern = /^https?:\/\/(www\.)?github\.com\/[\w-]+\/[\w.-]+\/?$/;
        if (!githubPattern.test(url)) {
            return 'Please enter a valid GitHub repository URL';
        }

        return null;
    };

    const validatePort = (port) => {
        if (!port) return 'Port is required';

        const portNum = parseInt(port);
        if (isNaN(portNum) || portNum < 1 || portNum > 65535) {
            return 'Port must be between 1 and 65535';
        }

        return null;
    };

    const handleChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({
            ...prev,
            [name]: value
        }));

        // Clear error when user starts typing
        if (errors[name]) {
            setErrors(prev => ({
                ...prev,
                [name]: null
            }));
        }
    };

    const handleSubmit = (e) => {
        e.preventDefault();

        // Validate all fields
        const newErrors = {};

        const urlError = validateGithubUrl(formData.github_url);
        if (urlError) newErrors.github_url = urlError;

        const containerPortError = validatePort(formData.container_port);
        if (containerPortError) newErrors.container_port = containerPortError;

        const hostPortError = validatePort(formData.host_port);
        if (hostPortError) newErrors.host_port = hostPortError;

        // If there are errors, don't submit
        if (Object.keys(newErrors).length > 0) {
            setErrors(newErrors);
            return;
        }

        // Submit the form
        onSubmit({
            github_url: formData.github_url,
            instance_name: formData.instance_name || null,
            container_port: parseInt(formData.container_port),
            host_port: parseInt(formData.host_port),
        });
    };

    return (
        <form onSubmit={handleSubmit} className="space-y-6">
            {/* GitHub URL */}
            <div>
                <label htmlFor="github_url" className="block text-sm font-medium text-foreground mb-2">
                    <div className="flex items-center gap-2">
                        <Github className="w-4 h-4" />
                        <span>GitHub Repository URL</span>
                        <span className="text-destructive">*</span>
                    </div>
                </label>
                <input
                    type="text"
                    id="github_url"
                    name="github_url"
                    value={formData.github_url}
                    onChange={handleChange}
                    disabled={isDeploying}
                    placeholder="https://github.com/username/repository"
                    className={cn(
                        "w-full px-4 py-2.5 bg-secondary border rounded-lg",
                        "text-foreground placeholder:text-muted-foreground",
                        "focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent",
                        "disabled:opacity-50 disabled:cursor-not-allowed",
                        "transition-colors",
                        errors.github_url ? "border-destructive" : "border-border"
                    )}
                />
                {errors.github_url && (
                    <p className="mt-1.5 text-sm text-destructive">{errors.github_url}</p>
                )}
                <p className="mt-1.5 text-xs text-muted-foreground">
                    Repository must contain a Dockerfile
                </p>
            </div>

            {/* Instance Name */}
            <div>
                <label htmlFor="instance_name" className="block text-sm font-medium text-foreground mb-2">
                    <div className="flex items-center gap-2">
                        <Server className="w-4 h-4" />
                        <span>Instance Name</span>
                        <span className="text-muted-foreground text-xs">(Optional)</span>
                    </div>
                </label>
                <input
                    type="text"
                    id="instance_name"
                    name="instance_name"
                    value={formData.instance_name}
                    onChange={handleChange}
                    disabled={isDeploying}
                    placeholder="my-ml-model (auto-generated if empty)"
                    className={cn(
                        "w-full px-4 py-2.5 bg-secondary border border-border rounded-lg",
                        "text-foreground placeholder:text-muted-foreground",
                        "focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent",
                        "disabled:opacity-50 disabled:cursor-not-allowed",
                        "transition-colors"
                    )}
                />
                <p className="mt-1.5 text-xs text-muted-foreground">
                    Custom name for your EC2 instance
                </p>
            </div>

            {/* Port Configuration */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Container Port */}
                <div>
                    <label htmlFor="container_port" className="block text-sm font-medium text-foreground mb-2">
                        <div className="flex items-center gap-2">
                            <Plug className="w-4 h-4" />
                            <span>Container Port</span>
                            <span className="text-destructive">*</span>
                        </div>
                    </label>
                    <input
                        type="number"
                        id="container_port"
                        name="container_port"
                        value={formData.container_port}
                        onChange={handleChange}
                        disabled={isDeploying}
                        placeholder="8000"
                        min="1"
                        max="65535"
                        className={cn(
                            "w-full px-4 py-2.5 bg-secondary border rounded-lg",
                            "text-foreground placeholder:text-muted-foreground",
                            "focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent",
                            "disabled:opacity-50 disabled:cursor-not-allowed",
                            "transition-colors",
                            errors.container_port ? "border-destructive" : "border-border"
                        )}
                    />
                    {errors.container_port && (
                        <p className="mt-1.5 text-sm text-destructive">{errors.container_port}</p>
                    )}
                    <p className="mt-1.5 text-xs text-muted-foreground">
                        Port your app listens on
                    </p>
                </div>

                {/* Host Port */}
                <div>
                    <label htmlFor="host_port" className="block text-sm font-medium text-foreground mb-2">
                        <div className="flex items-center gap-2">
                            <Plug className="w-4 h-4" />
                            <span>Host Port</span>
                            <span className="text-destructive">*</span>
                        </div>
                    </label>
                    <input
                        type="number"
                        id="host_port"
                        name="host_port"
                        value={formData.host_port}
                        onChange={handleChange}
                        disabled={isDeploying}
                        placeholder="8000"
                        min="1"
                        max="65535"
                        className={cn(
                            "w-full px-4 py-2.5 bg-secondary border rounded-lg",
                            "text-foreground placeholder:text-muted-foreground",
                            "focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent",
                            "disabled:opacity-50 disabled:cursor-not-allowed",
                            "transition-colors",
                            errors.host_port ? "border-destructive" : "border-border"
                        )}
                    />
                    {errors.host_port && (
                        <p className="mt-1.5 text-sm text-destructive">{errors.host_port}</p>
                    )}
                    <p className="mt-1.5 text-xs text-muted-foreground">
                        Port exposed on EC2
                    </p>
                </div>
            </div>

            {/* Submit Button */}
            <button
                type="submit"
                disabled={isDeploying}
                className={cn(
                    "w-full px-6 py-3 rounded-lg font-medium",
                    "flex items-center justify-center gap-2",
                    "transition-all duration-200",
                    isDeploying
                        ? "bg-secondary text-muted-foreground cursor-not-allowed"
                        : "bg-primary text-primary-foreground hover:bg-primary/90 hover:shadow-lg"
                )}
            >
                {isDeploying ? (
                    <>
                        <div className="w-5 h-5 border-2 border-muted-foreground border-t-transparent rounded-full animate-spin" />
                        <span>Deploying...</span>
                    </>
                ) : (
                    <>
                        <Rocket className="w-5 h-5" />
                        <span>Deploy Application</span>
                    </>
                )}
            </button>
        </form>
    );
}
