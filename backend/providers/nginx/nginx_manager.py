"""
NGINX Manager for the Automated Deployment Framework.
Handles NGINX installation, configuration, and management on remote EC2 instances.
"""

import logging
import time
from typing import Dict, Optional, Tuple
from ...core.utils import SSHClient

logger = logging.getLogger(__name__)


class NginxManager:
    """Manages NGINX operations on remote EC2 instances."""
    
    def __init__(self, hostname: str, username: str = 'ubuntu', key_file: Optional[str] = None):
        """
        Initialize NGINX Manager.
        
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
    
    def install_nginx(self) -> Tuple[bool, str]:
        """
        Install NGINX on the remote instance.
        
        Returns:
            Tuple of (success, message)
        """
        try:
            logger.info("Installing NGINX on remote instance...")
            
            # NGINX installation commands for Ubuntu
            APT = "sudo apt-get -o Dpkg::Lock::Timeout=120 -o Dpkg::Options::='--force-confdef' -o Dpkg::Options::='--force-confold'"
            install_commands = [
                f"{APT} update",
                
                # Install NGINX and certbot
                f"{APT} install -y nginx",
                
                # Start NGINX service
                "sudo systemctl start nginx",
                
                # Enable NGINX to start on boot
                "sudo systemctl enable nginx",
                
                # Verify installation
                "nginx -v"
            ]
            
            results = self.ssh.execute_commands(install_commands, stop_on_error=True)
            
            # Check if all commands succeeded
            if all(result[0] == 0 for result in results):
                logger.info("NGINX installed successfully")
                
                # Get NGINX version
                version_output = results[-1][2].strip()  # nginx outputs version to stderr
                return True, f"NGINX installed successfully: {version_output}"
            else:
                # Find first failed command
                for i, result in enumerate(results):
                    if result[0] != 0:
                        error_msg = f"Failed at command {i+1}: {install_commands[i]}\nError: {result[2]}"
                        logger.error(error_msg)
                        return False, error_msg
                        
        except Exception as e:
            error_msg = f"Error installing NGINX: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def check_nginx_installed(self) -> bool:
        """
        Check if NGINX is already installed.
        
        Returns:
            True if NGINX is installed
        """
        try:
            exit_code, stdout, stderr = self.ssh.execute_command("nginx -v")
            return exit_code == 0
        except:
            return False
    
    def create_site_config(self, 
                          app_name: str,
                          proxy_port: int,
                          server_name: str = "_",
                          enable_ssl: bool = False) -> Tuple[bool, str]:
        """
        Create NGINX site configuration for the application.
        
        Args:
            app_name: Application/deployment name
            proxy_port: Port where the application is running (e.g., 8000)
            server_name: Server name or domain (default: _ for catch-all)
            enable_ssl: Enable SSL configuration (future enhancement)
            
        Returns:
            Tuple of (success, message)
        """
        try:
            logger.info(f"Creating NGINX configuration for {app_name}")
            
            # Generate NGINX configuration
            nginx_config = f"""server {{
    listen 80;
    server_name {server_name};
    
    # Application proxy
    location / {{
        proxy_pass http://127.0.0.1:{proxy_port};
        proxy_http_version 1.1;
        
        # Proxy headers
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }}
    
    # Health check endpoint
    location /health {{
        access_log off;
        return 200 "healthy\\n";
        add_header Content-Type text/plain;
    }}
}}
"""
            
            # Write configuration to remote server
            config_path = f"/etc/nginx/sites-available/{app_name}"
            
            # Create temporary file with config
            temp_config = f"/tmp/{app_name}.conf"
            
            # Write config to temp file
            write_cmd = f"cat > {temp_config} << 'EOF'\n{nginx_config}\nEOF"
            exit_code, stdout, stderr = self.ssh.execute_command(write_cmd)
            
            if exit_code != 0:
                return False, f"Failed to create config file: {stderr}"
            
            # Move to sites-available with sudo
            move_cmd = f"sudo mv {temp_config} {config_path}"
            exit_code, stdout, stderr = self.ssh.execute_command(move_cmd)
            
            if exit_code != 0:
                return False, f"Failed to move config file: {stderr}"
            
            logger.info(f"NGINX configuration created at {config_path}")
            return True, f"Configuration created successfully"
            
        except Exception as e:
            error_msg = f"Error creating NGINX configuration: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def enable_site(self, app_name: str) -> Tuple[bool, str]:
        """
        Enable NGINX site configuration.
        
        Args:
            app_name: Application/deployment name
            
        Returns:
            Tuple of (success, message)
        """
        try:
            logger.info(f"Enabling NGINX site: {app_name}")
            
            # Remove default site if it exists
            remove_default_cmd = "sudo rm -f /etc/nginx/sites-enabled/default"
            self.ssh.execute_command(remove_default_cmd)
            
            # Create symlink to enable site
            symlink_cmd = f"sudo ln -sf /etc/nginx/sites-available/{app_name} /etc/nginx/sites-enabled/{app_name}"
            exit_code, stdout, stderr = self.ssh.execute_command(symlink_cmd)
            
            if exit_code != 0:
                return False, f"Failed to enable site: {stderr}"
            
            # Test NGINX configuration
            test_cmd = "sudo nginx -t"
            exit_code, stdout, stderr = self.ssh.execute_command(test_cmd)
            
            if exit_code != 0:
                return False, f"NGINX configuration test failed: {stderr}"
            
            logger.info(f"Site {app_name} enabled successfully")
            return True, "Site enabled successfully"
            
        except Exception as e:
            error_msg = f"Error enabling site: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def reload_nginx(self) -> Tuple[bool, str]:
        """
        Reload NGINX configuration without dropping connections.
        
        Returns:
            Tuple of (success, message)
        """
        try:
            logger.info("Reloading NGINX configuration...")
            
            reload_cmd = "sudo systemctl reload nginx"
            exit_code, stdout, stderr = self.ssh.execute_command(reload_cmd)
            
            if exit_code == 0:
                logger.info("NGINX reloaded successfully")
                return True, "NGINX reloaded successfully"
            else:
                return False, f"Failed to reload NGINX: {stderr}"
                
        except Exception as e:
            error_msg = f"Error reloading NGINX: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def check_nginx_status(self) -> Dict:
        """
        Check NGINX service status.
        
        Returns:
            Dictionary with NGINX status information
        """
        try:
            status_cmd = "sudo systemctl is-active nginx"
            exit_code, stdout, stderr = self.ssh.execute_command(status_cmd)
            
            is_running = (exit_code == 0 and stdout.strip() == 'active')
            
            return {
                'running': is_running,
                'status': stdout.strip() if exit_code == 0 else 'unknown',
                'error': stderr if exit_code != 0 else None
            }
            
        except Exception as e:
            logger.error(f"Error checking NGINX status: {str(e)}")
            return {
                'running': False,
                'status': 'error',
                'error': str(e)
            }
    
    def get_nginx_logs(self, log_type: str = 'error', tail: int = 50) -> str:
        """
        Get NGINX logs.
        
        Args:
            log_type: Type of log ('access' or 'error')
            tail: Number of lines to retrieve
            
        Returns:
            Log content
        """
        try:
            log_file = f"/var/log/nginx/{log_type}.log"
            command = f"sudo tail -n {tail} {log_file}"
            exit_code, stdout, stderr = self.ssh.execute_command(command)
            
            return stdout if exit_code == 0 else f"Error reading logs: {stderr}"
            
        except Exception as e:
            logger.error(f"Error getting NGINX logs: {str(e)}")
            return f"Error: {str(e)}"
    
    def disable_site(self, app_name: str) -> Tuple[bool, str]:
        """
        Disable NGINX site configuration.
        
        Args:
            app_name: Application/deployment name
            
        Returns:
            Tuple of (success, message)
        """
        try:
            logger.info(f"Disabling NGINX site: {app_name}")
            
            # Remove symlink
            remove_cmd = f"sudo rm -f /etc/nginx/sites-enabled/{app_name}"
            exit_code, stdout, stderr = self.ssh.execute_command(remove_cmd)
            
            if exit_code == 0:
                # Reload NGINX
                self.reload_nginx()
                return True, f"Site {app_name} disabled successfully"
            else:
                return False, f"Failed to disable site: {stderr}"
                
        except Exception as e:
            error_msg = f"Error disabling site: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def close(self):
        """Close SSH connection."""
        self.ssh.close()
