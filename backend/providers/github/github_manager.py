"""
GitHub Manager for the Automated Deployment Framework.
Handles GitHub repository operations and cloning to EC2 instances.
"""

import logging
from typing import Tuple, Optional
from ...core.utils import SSHClient, parse_github_url, sanitize_name

logger = logging.getLogger(__name__)


class GitHubManager:
    """Manages GitHub repository operations."""
    
    def __init__(self, hostname: str, username: str = 'ubuntu', key_file: Optional[str] = None):
        """
        Initialize GitHub Manager.
        
        Args:
            hostname: EC2 instance public IP or DNS
            username: SSH username
            key_file: Path to private key file
        """
        self.ssh = SSHClient(hostname, username, key_file)
        self.hostname = hostname
    
    def connect(self, max_wait: int = 180, retry_interval: int = 5,
                progress_callback: Optional[callable] = None) -> None:
        """
        Establish SSH connection to the instance.
        
        Args:
            max_wait: Maximum time to wait for SSH (default: 180s)
            retry_interval: Seconds between retries (default: 5s)
            progress_callback: Optional callback for progress updates
            
        Raises:
            TimeoutError: SSH not available within max_wait
            paramiko.AuthenticationException: Wrong credentials
        """
        self.ssh.connect(max_wait, retry_interval, progress_callback)
    
    def install_git(self) -> Tuple[bool, str]:
        """
        Install Git on the remote instance.
        
        Returns:
            Tuple of (success, message)
        """
        try:
            logger.info("Installing Git on remote instance...")
            
            # Check if Git is already installed
            exit_code, stdout, stderr = self.ssh.execute_command("git --version")
            
            if exit_code == 0:
                version = stdout.strip()
                logger.info(f"Git already installed: {version}")
                return True, f"Git already installed: {version}"
            APT = "sudo apt-get -o Dpkg::Lock::Timeout=120 -o Dpkg::Options::='--force-confdef' -o Dpkg::Options::='--force-confold'"
            commands = [
                # Install git if not present
                f"{APT} update",
                f"{APT} install -y git",
            ]
            
            results = self.ssh.execute_commands(commands, stop_on_error=True)
            
            if all(result[0] == 0 for result in results):
                # Get Git version
                exit_code, stdout, stderr = self.ssh.execute_command("git --version")
                version = stdout.strip()
                
                success_msg = f"Git installed successfully: {version}"
                logger.info(success_msg)
                return True, success_msg
            else:
                error_msg = "Failed to install Git"
                logger.error(error_msg)
                return False, error_msg
                
        except Exception as e:
            error_msg = f"Error installing Git: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def clone_repository(self, 
                        repo_url: str,
                        destination: str = None,
                        branch: str = 'main',
                        token: Optional[str] = None) -> Tuple[bool, str, str]:
        """
        Clone GitHub repository to the remote instance.
        
        Args:
            repo_url: GitHub repository URL
            destination: Destination directory (default: repo name in home directory)
            branch: Branch to clone (default: main)
            token: GitHub token for private repositories
            
        Returns:
            Tuple of (success, message, clone_path)
        """
        try:
            logger.info(f"Cloning repository: {repo_url}")
            
            # Ensure Git is installed
            git_installed, msg = self.install_git()
            if not git_installed:
                return False, f"Failed to install Git: {msg}", ""
            
            # Parse repository URL
            owner, repo_name = parse_github_url(repo_url)
            
            # Determine destination path
            if destination is None:
                destination = f"~/{sanitize_name(repo_name)}"
            
            # Prepare clone URL with token if provided
            clone_url = repo_url
            if token:
                # Convert HTTPS URL to authenticated URL
                if repo_url.startswith('https://github.com/'):
                    clone_url = repo_url.replace('https://github.com/', f'https://{token}@github.com/')
            
            # Remove existing directory if it exists
            self.ssh.execute_command(f"rm -rf {destination}")
            
            # Clone repository
            clone_command = f"git clone -b {branch} {clone_url} {destination}"
            
            # If token is used, don't log the full command
            if token:
                logger.info(f"Cloning repository with authentication to {destination}")
            else:
                logger.info(f"Executing: {clone_command}")
            
            exit_code, stdout, stderr = self.ssh.execute_command(clone_command, timeout=300)
            
            if exit_code == 0:
                # Get absolute path
                exit_code, abs_path, _ = self.ssh.execute_command(f"readlink -f {destination}")
                clone_path = abs_path.strip()
                
                success_msg = f"Repository cloned successfully to {clone_path}"
                logger.info(success_msg)
                return True, success_msg, clone_path
            else:
                # Try with master branch if main fails
                if branch == 'main' and 'not found' in stderr.lower():
                    logger.info("Branch 'main' not found, trying 'master'")
                    return self.clone_repository(repo_url, destination, 'master', token)
                
                error_msg = f"Failed to clone repository.\nStdout: {stdout}\nStderr: {stderr}"
                logger.error(error_msg)
                return False, error_msg, ""
                
        except Exception as e:
            error_msg = f"Error cloning repository: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, ""
    
    def pull_latest(self, repo_path: str) -> Tuple[bool, str]:
        """
        Pull latest changes from repository.
        
        Args:
            repo_path: Path to repository on remote instance
            
        Returns:
            Tuple of (success, message)
        """
        try:
            logger.info(f"Pulling latest changes for {repo_path}")
            
            command = f"cd {repo_path} && git pull"
            exit_code, stdout, stderr = self.ssh.execute_command(command)
            
            if exit_code == 0:
                success_msg = f"Successfully pulled latest changes"
                logger.info(success_msg)
                return True, success_msg
            else:
                error_msg = f"Failed to pull changes: {stderr}"
                logger.error(error_msg)
                return False, error_msg
                
        except Exception as e:
            error_msg = f"Error pulling changes: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def get_current_branch(self, repo_path: str) -> str:
        """
        Get current branch of repository.
        
        Args:
            repo_path: Path to repository on remote instance
            
        Returns:
            Current branch name
        """
        try:
            command = f"cd {repo_path} && git branch --show-current"
            exit_code, stdout, stderr = self.ssh.execute_command(command)
            
            if exit_code == 0:
                return stdout.strip()
            else:
                return "unknown"
                
        except Exception as e:
            logger.error(f"Error getting current branch: {str(e)}")
            return "unknown"
    
    def get_commit_hash(self, repo_path: str) -> str:
        """
        Get current commit hash of repository.
        
        Args:
            repo_path: Path to repository on remote instance
            
        Returns:
            Current commit hash
        """
        try:
            command = f"cd {repo_path} && git rev-parse HEAD"
            exit_code, stdout, stderr = self.ssh.execute_command(command)
            
            if exit_code == 0:
                return stdout.strip()[:8]  # Short hash
            else:
                return "unknown"
                
        except Exception as e:
            logger.error(f"Error getting commit hash: {str(e)}")
            return "unknown"
    
    def verify_project_files(self, repo_path: str, required_files: list = None) -> Tuple[bool, list]:
        """
        Verify that required files exist in the repository.
        
        Args:
            repo_path: Path to repository on remote instance
            required_files: List of required files (default: ['Dockerfile'])
            
        Returns:
            Tuple of (all_exist, missing_files)
        """
        if required_files is None:
            required_files = ['Dockerfile']
        
        try:
            logger.info(f"Verifying project files in {repo_path}")
            
            missing_files = []
            
            for file in required_files:
                command = f"test -f {repo_path}/{file} && echo 'exists' || echo 'missing'"
                exit_code, stdout, stderr = self.ssh.execute_command(command)
                
                if 'missing' in stdout:
                    missing_files.append(file)
            
            if missing_files:
                logger.warning(f"Missing required files: {missing_files}")
                return False, missing_files
            else:
                logger.info("All required files present")
                return True, []
                
        except Exception as e:
            logger.error(f"Error verifying project files: {str(e)}")
            return False, required_files
    
    def close(self):
        """Close SSH connection."""
        self.ssh.close()
