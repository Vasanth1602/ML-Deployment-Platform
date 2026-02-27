"""
Input validation for the Automated Deployment Framework.
Validates GitHub URLs, project structure, and configurations.
"""

import re
import logging
import validators
from typing import Tuple, List, Optional
import requests

logger = logging.getLogger(__name__)


def validate_github_url(url: str) -> Tuple[bool, Optional[str]]:
    """
    Validate GitHub repository URL.
    
    Args:
        url: GitHub repository URL
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not url:
        return False, "GitHub URL is required"
    
    # Check if it's a valid URL
    if not validators.url(url):
        return False, "Invalid URL format"
    
    # Check if it's a GitHub URL
    github_patterns = [
        r'^https?://github\.com/[\w-]+/[\w.-]+/?$',
        r'^https?://github\.com/[\w-]+/[\w.-]+\.git$',
        r'^git@github\.com:[\w-]+/[\w.-]+\.git$'
    ]
    
    if not any(re.match(pattern, url) for pattern in github_patterns):
        return False, "URL must be a valid GitHub repository URL"
    
    return True, None


def validate_github_repo_exists(url: str, token: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """
    Check if GitHub repository exists and is accessible.
    
    Args:
        url: GitHub repository URL
        token: Optional GitHub token for private repos
        
    Returns:
        Tuple of (exists, error_message)
    """
    try:
        # Convert GitHub URL to API URL
        url = url.rstrip('/')
        if url.endswith('.git'):
            url = url[:-4]
        
        parts = url.split('/')
        owner = parts[-2]
        repo = parts[-1]
        
        api_url = f"https://api.github.com/repos/{owner}/{repo}"
        
        headers = {}
        if token:
            headers['Authorization'] = f"token {token}"
        
        response = requests.get(api_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            return True, None
        elif response.status_code == 404:
            return False, "Repository not found or not accessible"
        elif response.status_code == 403:
            return False, "Access forbidden. Repository may be private (provide GitHub token)"
        else:
            return False, f"Failed to validate repository (status code: {response.status_code})"
            
    except Exception as e:
        logger.error(f"Error validating GitHub repository: {str(e)}")
        return False, f"Error validating repository: {str(e)}"


def validate_project_structure(repo_url: str, required_files: List[str] = None) -> Tuple[bool, Optional[str]]:
    """
    Validate that repository contains required files for deployment.
    
    Args:
        repo_url: GitHub repository URL
        required_files: List of required files (default: ['Dockerfile'])
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if required_files is None:
        required_files = ['Dockerfile']
    
    try:
        # Convert GitHub URL to raw content URL
        url = repo_url.rstrip('/')
        if url.endswith('.git'):
            url = url[:-4]
        
        parts = url.split('/')
        owner = parts[-2]
        repo = parts[-1]
        
        # Check each required file
        missing_files = []
        for file in required_files:
            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/{file}"
            
            # Try main branch
            response = requests.head(raw_url, timeout=10)
            
            # If not found, try master branch
            if response.status_code == 404:
                raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/master/{file}"
                response = requests.head(raw_url, timeout=10)
            
            if response.status_code != 200:
                missing_files.append(file)
        
        if missing_files:
            return False, f"Missing required files: {', '.join(missing_files)}"
        
        return True, None
        
    except Exception as e:
        logger.error(f"Error validating project structure: {str(e)}")
        return False, f"Error validating project structure: {str(e)}"


def validate_aws_credentials(access_key: str, secret_key: str) -> Tuple[bool, Optional[str]]:
    """
    Validate AWS credentials format.
    
    Args:
        access_key: AWS Access Key ID
        secret_key: AWS Secret Access Key
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not access_key:
        return False, "AWS Access Key ID is required"
    
    if not secret_key:
        return False, "AWS Secret Access Key is required"
    
    # Basic format validation
    if not re.match(r'^[A-Z0-9]{20}$', access_key):
        return False, "Invalid AWS Access Key ID format"
    
    if len(secret_key) != 40:
        return False, "Invalid AWS Secret Access Key format"
    
    return True, None


def validate_instance_type(instance_type: str) -> Tuple[bool, Optional[str]]:
    """
    Validate EC2 instance type.
    
    Args:
        instance_type: EC2 instance type (e.g., t2.micro)
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Common instance types
    valid_types = [
        't2.micro', 't2.small', 't2.medium', 't2.large',
        't3.micro', 't3.small', 't3.medium', 't3.large',
        't3a.micro', 't3a.small', 't3a.medium', 't3a.large',
        'm5.large', 'm5.xlarge', 'm5.2xlarge',
        'c5.large', 'c5.xlarge', 'c5.2xlarge'
    ]
    
    if instance_type not in valid_types:
        return False, f"Invalid instance type. Common types: {', '.join(valid_types[:8])}"
    
    return True, None


def validate_port(port: int) -> Tuple[bool, Optional[str]]:
    """
    Validate port number.
    
    Args:
        port: Port number
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(port, int):
        return False, "Port must be an integer"
    
    if port < 1 or port > 65535:
        return False, "Port must be between 1 and 65535"
    
    # Warn about privileged ports
    if port < 1024:
        logger.warning(f"Port {port} is a privileged port and may require root access")
    
    return True, None


def validate_deployment_config(config: dict) -> Tuple[bool, List[str]]:
    """
    Validate complete deployment configuration.
    
    Args:
        config: Deployment configuration dictionary
        
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    # Validate GitHub URL
    if 'github_url' in config:
        is_valid, error = validate_github_url(config['github_url'])
        if not is_valid:
            errors.append(f"GitHub URL: {error}")
    else:
        errors.append("GitHub URL is required")
    
    # Validate instance type if provided
    if 'instance_type' in config:
        is_valid, error = validate_instance_type(config['instance_type'])
        if not is_valid:
            errors.append(f"Instance type: {error}")
    
    # Validate port if provided
    if 'port' in config:
        is_valid, error = validate_port(config['port'])
        if not is_valid:
            errors.append(f"Port: {error}")
    
    return len(errors) == 0, errors
