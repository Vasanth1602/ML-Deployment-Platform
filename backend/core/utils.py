"""
Utility functions for the Automated Deployment Framework.
Provides SSH connection, remote command execution, and helper utilities.
"""

import os
import time
import socket
import logging
import paramiko
import boto3
from typing import Tuple, Optional, List
import requests

from ..config import config

logger = logging.getLogger(__name__)

PEM_PATH = config.PEM_KEY_PATH


def is_inside_aws():
    # Priority 1: ENV (reliable)
    if os.getenv("RUNNING_IN_AWS") == "true":
        return True

    # Fallback: metadata (best effort)
    try:
        requests.get(
            "http://169.254.169.254/latest/meta-data/",
            timeout=1
        )
        return True
    except:
        return False


def resolve_hostname(instance) -> str:
    """
    Decide whether to use private or public IP for SSH.

    - Inside AWS → use private IP (same VPC, avoids hairpinning through IGW)
    - Outside AWS (local dev) → use public IP
    """
    if is_inside_aws() and instance.private_ip_address:
        logger.info(f"[SSH] Using PRIVATE IP: {instance.private_ip_address}")
        return instance.private_ip_address

    logger.info(f"[SSH] Using PUBLIC IP: {instance.public_ip_address}")
    return instance.public_ip_address


def load_pem_from_secrets_manager() -> Optional[str]:
    """
    Fetch the SSH private key from AWS Secrets Manager and write it to disk.

    Uses PEM_SECRET_NAME env var to find the secret.
    Returns the path to the written PEM file, or None if PEM_SECRET_NAME is not set
    (e.g. local dev without Secrets Manager).

    Called once at Flask app startup (create_app) so the key is ready
    before any deployment SSH attempt.
    """
    secret_name = config.PEM_SECRET_NAME

    if not secret_name:
        logger.warning(
            '[PEM] PEM_SECRET_NAME not set — skipping Secrets Manager fetch. '
            'SSH deployments will fail unless the key exists at %s', PEM_PATH
        )
        return None

    region = os.getenv('AWS_REGION', 'ap-south-1')

    try:
        client = boto3.client('secretsmanager', region_name=region)
        response = client.get_secret_value(SecretId=secret_name)
        pem_content = response['SecretString']

        with open(PEM_PATH, 'w') as f:
            f.write(pem_content)
        os.chmod(PEM_PATH, 0o600)

        logger.info('[OK] PEM key fetched from Secrets Manager → %s', PEM_PATH)
        return PEM_PATH

    except Exception as e:
        logger.error('[PEM] Failed to fetch PEM from Secrets Manager: %s', e)
        raise



class SSHClient:
    """Wrapper for SSH connections and remote command execution."""
    
    def __init__(self, hostname: str, username: str = 'ubuntu', key_file: Optional[str] = None):
        """
        Initialize SSH client.
        
        Args:
            hostname: EC2 instance public IP or DNS
            username: SSH username (default: ubuntu)
            key_file: Path to private key file
        """
        self.hostname = hostname
        self.username = username

        import os
        # if key_file and not os.path.isabs(key_file):
        #     # EC2_KEY_DIR controls where PEM files are resolved from.
        #     # Localhost default: project root (where the .pem sits after download).
        #     # Docker / ECS: set EC2_KEY_DIR=/app/backend in the environment.
        #     _key_base = os.getenv(
        #         'EC2_KEY_DIR',
        #         os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        #     )
        #     key_file = os.path.join(_key_base, key_file)

        self.key_file = key_file
        self.client = None
        
    def connect(self, max_wait: int = 300, retry_interval: int = 5, 
                progress_callback: Optional[callable] = None) -> None:
        """
        Establish SSH connection with intelligent retry logic.
        
        Args:
            max_wait: Maximum time to wait in seconds (default: 180s = 3 minutes)
            retry_interval: Seconds between retries (default: 5s)
            progress_callback: Optional callback function for progress updates
                              Called with (step, message, status, data)
            
        Raises:
            TimeoutError: SSH not available within max_wait
            paramiko.AuthenticationException: Wrong credentials
        """
        import socket
        
        start_time = time.time()
        max_attempts = max_wait // retry_interval
        attempt = 0
        
        # Emit initial progress
        if progress_callback:
            progress_callback(
                step='SSH Connection',
                message='Waiting for SSH to become available (cloud-init may be running)...',
                status='in_progress',
                data={}
            )
        
        while True:
            attempt += 1
            elapsed = int(time.time() - start_time)
            remaining = max_wait - elapsed
            
            # Check timeout
            if elapsed >= max_wait:
                error_msg = f"SSH not available after {max_wait}s. Check security groups and instance logs."
                logger.error(error_msg)
                if progress_callback:
                    progress_callback(
                        step='SSH Connection',
                        message=f'[ERROR] {error_msg}',
                        status='error',
                        data={}
                    )
                raise TimeoutError(error_msg)
            
            try:
                logger.error(f"[SSH-DEBUG] Attempting SSH connection to {self.hostname} key={self.key_file} (attempt {attempt}/{max_attempts})")
                # logger.debug(f"Attempting SSH connection to {self.hostname} (attempt {attempt}/{max_attempts})")
                
                # Recreate the paramiko client on EVERY attempt.
                # After any connection failure, the previous client object is in a
                # broken internal state (transport thread crashed, socket closed).
                # Reusing it causes persistent banner errors. Fresh client = clean slate.
                self.client = paramiko.SSHClient()
                self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                # Attempt connection
                # NOTE: keepalive_interval is NOT a valid paramiko connect() argument.
                # Use transport.set_keepalive() after a successful connection instead.
                if self.key_file:
                    self.client.connect(
                        hostname=self.hostname,
                        username=self.username,
                        key_filename=self.key_file,
                        timeout=20,           # increased for Docker bridge latency
                        banner_timeout=30,    # EC2 sshd needs longer to send banner
                        auth_timeout=20,
                    )
                else:
                    self.client.connect(
                        hostname=self.hostname,
                        username=self.username,
                        timeout=20,           # increased for Docker bridge latency
                        banner_timeout=30,    # EC2 sshd needs longer to send banner
                        auth_timeout=20,
                    )
                
                # Set keepalive AFTER connecting (correct paramiko API)
                transport = self.client.get_transport()
                if transport:
                    transport.set_keepalive(30)  # send keepalive every 30 seconds
                
                # Success!
                success_msg = f"SSH connection established after {elapsed}s ({attempt} attempts)"
                logger.info(success_msg)
                if progress_callback:
                    progress_callback(
                        step='SSH Connection',
                        message=f'[OK] {success_msg}',
                        status='success',
                        data={}
                    )
                return
                
            except paramiko.AuthenticationException as e:
                # Auth error = SSH is ready but credentials wrong
                # Don't retry on auth errors
                error_msg = f"SSH authentication failed: {str(e)}"
                logger.error(error_msg)
                if progress_callback:
                    progress_callback(
                        step='SSH Connection',
                        message=f'[ERROR] {error_msg}',
                        status='error',
                        data={}
                    )
                raise
                
            except (socket.error, socket.timeout, paramiko.SSHException, EOFError) as e:
                # Expected errors during boot - classify and retry
                error_type = self._classify_ssh_error(e)
                
                logger.debug(f"SSH connection attempt {attempt} failed: {error_type} - {str(e)}")
                
                if progress_callback:
                    progress_callback(
                        step='SSH Connection',
                        message=f'[WAIT] SSH not ready ({error_type}), retrying {attempt}/{max_attempts} (~{remaining}s remaining)...',
                        status='in_progress',
                        data={}
                    )
                
                # Wait before retry
                time.sleep(retry_interval)
                
            except Exception as e:
                # Unexpected error — log and keep retrying until timeout
                logger.warning(f"Unexpected SSH error: {type(e).__name__}: {str(e)}")
                
                if progress_callback:
                    progress_callback(
                        step='SSH Connection',
                        message=f'[WARN] Unexpected error: {type(e).__name__}',
                        status='warning',
                        data={}
                    )
                
                # Continue retrying unless timeout reached
                if elapsed >= max_wait:
                    raise
                    
                time.sleep(retry_interval)
    
    def _classify_ssh_error(self, error: Exception) -> str:
        """
        Classify SSH connection errors for user-friendly messages.
        
        Args:
            error: The exception that occurred
            
        Returns:
            User-friendly error description
        """
        import socket
        
        if isinstance(error, socket.timeout):
            return "connection timeout"
        elif isinstance(error, ConnectionRefusedError):
            return "SSH daemon not started"
        elif isinstance(error, socket.gaierror):
            return "DNS resolution failed"
        elif "timed out" in str(error).lower():
            return "connection timeout"
        elif "refused" in str(error).lower():
            return "connection refused"
        elif "unreachable" in str(error).lower():
            return "network unreachable"
        else:
            return "SSH not ready"
    
    def execute_command(self, command: str, timeout: int = 300) -> Tuple[int, str, str]:
        """
        Execute a command on the remote server.
        
        Args:
            command: Command to execute
            timeout: Command timeout in seconds
            
        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        if not self.client:
            raise Exception("SSH client not connected")
        
        try:
            logger.info(f"Executing command: {command}")
            stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
            
            exit_code = stdout.channel.recv_exit_status()
            stdout_text = stdout.read().decode('utf-8')
            stderr_text = stderr.read().decode('utf-8')
            
            if exit_code == 0:
                logger.info(f"Command executed successfully")
            else:
                logger.warning(f"Command exited with code {exit_code}")
            
            return exit_code, stdout_text, stderr_text
            
        except Exception as e:
            logger.error(f"Error executing command: {str(e)}")
            raise
    
    def execute_commands(self, commands: List[str], stop_on_error: bool = True) -> List[Tuple[int, str, str]]:
        """
        Execute multiple commands sequentially.
        
        Args:
            commands: List of commands to execute
            stop_on_error: Stop execution if a command fails
            
        Returns:
            List of tuples (exit_code, stdout, stderr) for each command
        """
        results = []
        
        for cmd in commands:
            result = self.execute_command(cmd)
            results.append(result)
            
            if stop_on_error and result[0] != 0:
                logger.error(f"Command failed, stopping execution: {cmd}")
                break
        
        return results
    
    def close(self):
        """Close SSH connection."""
        if self.client:
            self.client.close()
            logger.info(f"SSH connection to {self.hostname} closed")


def wait_for_ssh(host, port=22, timeout=300, interval=5):
    print(f"[SSH-WAIT] Waiting for SSH banner on {host}:{port}...")

    start = time.time()

    while time.time() - start < timeout:
        try:
            sock = socket.create_connection((host, port), timeout=5)
            sock.settimeout(5)

            banner = sock.recv(1024).decode(errors="ignore")
            sock.close()

            if "SSH" in banner:
                print("[SSH-WAIT] ✅ SSH banner received")
                return True
            else:
                print(f"[SSH-WAIT] ⏳ Port open but no SSH banner yet: {banner.strip()}")

        except Exception as e:
            print(f"[SSH-WAIT] ⏳ Not ready: {e}")

        time.sleep(interval)

    raise TimeoutError("SSH not ready (banner not received)")


def check_url_health(url: str, timeout: int = 10, expected_status: int = 200) -> bool:
    """
    Check if a URL is accessible and returns expected status.
    
    Args:
        url: URL to check
        timeout: Request timeout in seconds
        expected_status: Expected HTTP status code
        
    Returns:
        True if URL is healthy, False otherwise
    """
    try:
        response = requests.get(url, timeout=timeout)
        return response.status_code == expected_status
    except Exception as e:
        logger.debug(f"Health check failed for {url}: {str(e)}")
        return False


def format_deployment_url(public_ip: str, port: int, protocol: str = 'http') -> str:
    """
    Format deployment URL from IP and port.
    
    Args:
        public_ip: Public IP address
        port: Application port
        protocol: Protocol (http or https)
        
    Returns:
        Formatted URL
    """
    return f"{protocol}://{public_ip}:{port}"


def parse_github_url(url: str) -> Tuple[str, str]:
    """
    Parse GitHub URL to extract owner and repository name.
    
    Args:
        url: GitHub repository URL
        
    Returns:
        Tuple of (owner, repo_name)
    """
    # Remove .git suffix if present
    url = url.rstrip('/')
    if url.endswith('.git'):
        url = url[:-4]
    
    # Extract owner and repo from URL
    parts = url.split('/')
    if len(parts) >= 2:
        repo_name = parts[-1]
        owner = parts[-2]
        return owner, repo_name
    
    raise ValueError(f"Invalid GitHub URL: {url}")


def sanitize_name(name: str) -> str:
    """
    Sanitize a name for use in AWS resources.
    
    Args:
        name: Name to sanitize
        
    Returns:
        Sanitized name
    """
    # Replace invalid characters with hyphens
    sanitized = ''.join(c if c.isalnum() or c in '-_' else '-' for c in name)
    # Remove consecutive hyphens
    while '--' in sanitized:
        sanitized = sanitized.replace('--', '-')
    # Remove leading/trailing hyphens
    sanitized = sanitized.strip('-')
    return sanitized.lower()
