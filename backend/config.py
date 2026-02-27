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
    
    # AWS Configuration
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
    AWS_DEFAULT_INSTANCE_TYPE = os.getenv('AWS_DEFAULT_INSTANCE_TYPE', 't2.micro')
    AWS_KEY_PAIR_NAME = os.getenv('AWS_KEY_PAIR_NAME')
    
    # EC2 Configuration
    EC2_AMI_ID = os.getenv('EC2_AMI_ID', 'ami-0c55b159cbfafe1f0')
    EC2_INSTANCE_TYPE = os.getenv('EC2_INSTANCE_TYPE', 't2.micro')
    EC2_VOLUME_SIZE = int(os.getenv('EC2_VOLUME_SIZE', '20'))
    
    # Security Group Configuration
    SECURITY_GROUP_NAME = os.getenv('SECURITY_GROUP_NAME', 'ml-deployment-sg')
    ALLOWED_SSH_IP = os.getenv('ALLOWED_SSH_IP', '0.0.0.0/0')
    
    # Application Configuration
    APP_PORT = int(os.getenv('APP_PORT', '5000'))
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Docker Configuration
    DOCKER_CONTAINER_PORT = int(os.getenv('DOCKER_CONTAINER_PORT', '8000'))
    DOCKER_HOST_PORT = int(os.getenv('DOCKER_HOST_PORT', '8000'))
    
    # Deployment Settings
    MAX_DEPLOYMENT_TIME = int(os.getenv('MAX_DEPLOYMENT_TIME', '600'))
    HEALTH_CHECK_INTERVAL = int(os.getenv('HEALTH_CHECK_INTERVAL', '10'))
    HEALTH_CHECK_RETRIES = int(os.getenv('HEALTH_CHECK_RETRIES', '5'))
    
    # GitHub Configuration
    GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'deployment.log')
    
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
        
        if not cls.AWS_ACCESS_KEY_ID:
            errors.append("AWS_ACCESS_KEY_ID is required")
        if not cls.AWS_SECRET_ACCESS_KEY:
            errors.append("AWS_SECRET_ACCESS_KEY is required")
        if not cls.AWS_KEY_PAIR_NAME:
            errors.append("AWS_KEY_PAIR_NAME is required")
            
        return errors
    
    @classmethod
    def is_configured(cls):
        """Check if all required configurations are set."""
        return len(cls.validate()) == 0

# Create a singleton instance
config = Config()

# Add backward compatibility property after class is defined
Config.SECURITY_GROUP_RULES = Config.get_security_group_rules()
