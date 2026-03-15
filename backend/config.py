"""
Configuration management for the Automated Deployment Framework.
Loads environment variables and provides configuration settings.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration class."""

    # ── AWS Configuration ─────────────────────────────────────────────────────
    # NOTE: AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY are intentionally absent.
    # Credentials are resolved automatically by boto3 via the IAM Task Role
    # (ECS container metadata endpoint) in production, or via `aws configure`
    # / AWS_PROFILE for local development. Never put long-lived keys here.
    AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
    AWS_KEY_PAIR_NAME = os.getenv('AWS_KEY_PAIR_NAME')
    
    # EC2 Configuration
    # ⚠️  No default — AMI IDs are region-specific. Must be set explicitly in .env.
    EC2_AMI_ID = os.getenv('EC2_AMI_ID')
    EC2_INSTANCE_TYPE = os.getenv('EC2_INSTANCE_TYPE', 't2.micro')
    EC2_VOLUME_SIZE = int(os.getenv('EC2_VOLUME_SIZE', '20'))
    # ECS only — leave blank for local dev (default VPC is used)
    EC2_VPC_ID = os.getenv('EC2_VPC_ID', '')
    EC2_SUBNET_ID = os.getenv('EC2_SUBNET_ID', '')
    
    # Security Group Configuration
    SECURITY_GROUP_NAME = os.getenv('SECURITY_GROUP_NAME', 'ml-deployment-sg')
    ALLOWED_SSH_IP = os.getenv('ALLOWED_SSH_IP', '0.0.0.0/0')
    
    # Application Configuration
    APP_PORT = int(os.getenv('APP_PORT', '5000'))
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    # ⚠️  Defaults are intentionally weak — must be overridden via env in production.
    # validate() raises errors if production mode detects default values.
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

    # JWT Authentication
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', os.getenv('SECRET_KEY', 'dev-jwt-secret-change-in-production'))
    JWT_EXPIRY_HOURS = int(os.getenv('JWT_EXPIRY_HOURS', '1'))

    # First-Admin Bootstrap
    ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', '')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', '')

    # CORS / Origin Configuration
    # Comma-separated list of allowed origins for API (Flask-CORS) and WebSocket (SocketIO).
    # Production example: https://yourdomain.com
    # Development: left empty so dev-specific origins are appended automatically by app.py
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', '')
    FRONTEND_URL = os.getenv('FRONTEND_URL', '')
    DEV_CORS_ORIGINS = os.getenv(
        'DEV_CORS_ORIGINS',
        'http://localhost:5173,http://localhost:80,http://localhost:3000'
    )

    @classmethod
    def get_cors_origins_list(cls) -> list:
        """Return CORS_ORIGINS as a parsed list; falls back to dev list in development."""
        if cls.CORS_ORIGINS:
            return [o.strip() for o in cls.CORS_ORIGINS.split(',') if o.strip()]
        if cls.FLASK_ENV == 'development':
            return [o.strip() for o in cls.DEV_CORS_ORIGINS.split(',') if o.strip()]
        return []
    
    # Docker Configuration
    DOCKER_CONTAINER_PORT = int(os.getenv('DOCKER_CONTAINER_PORT', '8000'))
    DOCKER_HOST_PORT = int(os.getenv('DOCKER_HOST_PORT', '8000'))
    
    # Deployment Settings
    MAX_DEPLOYMENT_TIME = int(os.getenv('MAX_DEPLOYMENT_TIME', '600'))
    HEALTH_CHECK_INTERVAL = int(os.getenv('HEALTH_CHECK_INTERVAL', '10'))
    HEALTH_CHECK_RETRIES = int(os.getenv('HEALTH_CHECK_RETRIES', '5'))
    # EC2 readiness wait (after instance enters running)
    EC2_READY_TIMEOUT = int(os.getenv('EC2_READY_TIMEOUT', '300'))
    EC2_READY_POLL_INTERVAL = int(os.getenv('EC2_READY_POLL_INTERVAL', '10'))
    # SSH readiness wait (after EC2 status checks pass)
    SSH_READY_TIMEOUT = int(os.getenv('SSH_READY_TIMEOUT', '420'))
    SSH_RETRY_INTERVAL = int(os.getenv('SSH_RETRY_INTERVAL', '5'))
    
    # GitHub Configuration
    GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'deployment.log')
    
    # PEM / SSH Key Configuration
    PEM_SECRET_NAME = os.getenv('PEM_SECRET_NAME', '')
    # PEM key path — single source of truth for where the key is written and read
    PEM_KEY_PATH = os.getenv('PEM_KEY_PATH', '/app/ml-deploy-key.pem')

    # Static folder — must point to Vite's build output, not source
    STATIC_FOLDER = os.getenv('STATIC_FOLDER', '../frontend/dist')

    # NGINX Configuration
    ENABLE_NGINX = os.getenv('ENABLE_NGINX', 'true').lower() == 'true'
    NGINX_HTTP_PORT = int(os.getenv('NGINX_HTTP_PORT', '80'))
    NGINX_HTTPS_PORT = int(os.getenv('NGINX_HTTPS_PORT', '443'))
    ENABLE_SSL = os.getenv('ENABLE_SSL', 'false').lower() == 'true'
    SSL_EMAIL = os.getenv('SSL_EMAIL', '')
    
    # Security Group Rules
    @classmethod
    def get_security_group_rules(cls):
        """Get security group rules based on NGINX configuration."""
        rules = [
            {
                'IpProtocol': 'tcp',
                'FromPort': 22,
                'ToPort': 22,
                'IpRanges': [{'CidrIp': cls.ALLOWED_SSH_IP, 'Description': 'SSH access'}]
            },
            {
                'IpProtocol': 'tcp',
                'FromPort': 80,
                'ToPort': 80,
                'IpRanges': [{'CidrIp': '0.0.0.0/0', 'Description': 'HTTP access'}]
            },
            {
                'IpProtocol': 'tcp',
                'FromPort': 443,
                'ToPort': 443,
                'IpRanges': [{'CidrIp': '0.0.0.0/0', 'Description': 'HTTPS access'}]
            }
        ]
        
        # Only add Docker port if NGINX is disabled (direct access mode)
        if not cls.ENABLE_NGINX:
            rules.append({
                'IpProtocol': 'tcp',
                'FromPort': cls.DOCKER_HOST_PORT,
                'ToPort': cls.DOCKER_HOST_PORT,
                'IpRanges': [{'CidrIp': '0.0.0.0/0', 'Description': 'Application direct access'}]
            })
        
        return rules
    
    @classmethod
    def validate(cls):
        """Validate required configuration values."""
        errors = []

        # AWS credentials are NOT validated here — they come from the IAM Task
        # Role at runtime (no static keys anywhere in this codebase).
        if not cls.AWS_KEY_PAIR_NAME:
            errors.append('AWS_KEY_PAIR_NAME is required')

        if not cls.EC2_AMI_ID:
            errors.append('EC2_AMI_ID is required (AMI IDs are region-specific — no safe default exists)')

        # In production, reject known-weak default secrets
        if cls.FLASK_ENV != 'development':
            if cls.SECRET_KEY in ('dev-secret-key-change-in-production', ''):
                errors.append('SECRET_KEY must be set to a strong random value in production')
            if cls.JWT_SECRET_KEY in ('dev-jwt-secret-change-in-production', ''):
                errors.append('JWT_SECRET_KEY must be set to a strong random value in production')
            if not cls.FRONTEND_URL:
                errors.append('FRONTEND_URL must be set in production (required for SocketIO CORS)')
            if not cls.CORS_ORIGINS:
                errors.append('CORS_ORIGINS must be set in production')

        return errors
    
    @classmethod
    def is_configured(cls):
        """Check if all required configurations are set."""
        return len(cls.validate()) == 0

# Create a singleton instance
config = Config()

# Add backward compatibility property after class is defined
Config.SECURITY_GROUP_RULES = Config.get_security_group_rules()
