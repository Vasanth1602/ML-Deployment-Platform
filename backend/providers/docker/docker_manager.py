"""
Docker Manager for the Automated Deployment Framework.
Handles Docker installation, image building, and container management on remote EC2 instances.
"""

import logging
import time
from typing import Dict, Optional, List, Tuple
from ...core.utils import SSHClient

logger = logging.getLogger(__name__)


class DockerManager:
    """Manages Docker operations on remote EC2 instances."""
    
    def __init__(self, hostname: str, username: str = 'ubuntu', key_file: Optional[str] = None):
        """
        Initialize Docker Manager.
        
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
    
    def install_docker(self) -> Tuple[bool, str]:
        """
        Install Docker Engine on the remote instance.
        
        Returns:
            Tuple of (success, message)
        """
        try:
            logger.info("Installing Docker on remote instance...")
            
            logger.info("Waiting for cloud-init and boot processes to finish...")
            # cloud-init blocks until all automated boot scripts (like unattended-upgrades) finish
            self.ssh.execute_command("cloud-init status --wait || true", timeout=600)
            
            logger.info("System boot complete. Ready for Docker installation.")
            
            # We use native apt lock waits to prevent any lingering race conditions
            APT = "sudo apt-get -o Dpkg::Lock::Timeout=120 -o Dpkg::Options::='--force-confdef' -o Dpkg::Options::='--force-confold'"
            
            # Docker installation commands for Ubuntu
            install_commands = [
                # Update package index
                f"{APT} update",
                
                # Install prerequisites
                f"{APT} install -y ca-certificates curl gnupg lsb-release",
                
                # Add Docker's official GPG key
                "sudo mkdir -p /etc/apt/keyrings",
                "curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg || true",
                
                # Set up Docker repository
                'echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null',
                
                # Update package index again
                f"{APT} update",
                
                # Install Docker Engine
                f"{APT} install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin",
                
                # Add user to docker group
                f"sudo usermod -aG docker {self.ssh.username}",
                
                # Start Docker service
                "sudo systemctl start docker",
                "sudo systemctl enable docker",
                
                # Verify installation
                "sudo docker --version"
            ]
            
            results = self.ssh.execute_commands(install_commands, stop_on_error=True)
            
            # Check if all commands succeeded
            if all(result[0] == 0 for result in results):
                logger.info("Docker installed successfully")
                
                # Get Docker version
                version_output = results[-1][1].strip()
                return True, f"Docker installed successfully: {version_output}"
            else:
                # Find first failed command
                for i, result in enumerate(results):
                    if result[0] != 0:
                        error_msg = f"Failed at command {i+1}: {install_commands[i]}\nError: {result[2]}"
                        logger.error(error_msg)
                        return False, error_msg
                        
        except Exception as e:
            error_msg = f"Error installing Docker: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def check_docker_installed(self) -> bool:
        """
        Check if Docker is already installed.
        
        Returns:
            True if Docker is installed
        """
        try:
            exit_code, stdout, stderr = self.ssh.execute_command("sudo docker --version")
            return exit_code == 0
        except:
            return False
    
    def build_image(self, project_path: str, image_name: str, tag: str = 'latest') -> Tuple[bool, str]:
        """
        Build Docker image from Dockerfile.
        
        Args:
            project_path: Path to project directory containing Dockerfile
            image_name: Name for the Docker image
            tag: Image tag (default: latest)
            
        Returns:
            Tuple of (success, message)
        """
        try:
            logger.info(f"Building Docker image: {image_name}:{tag}")
            
            # Build command
            build_command = f"cd {project_path} && sudo docker build -t {image_name}:{tag} ."
            
            exit_code, stdout, stderr = self.ssh.execute_command(build_command, timeout=600)
            
            if exit_code == 0:
                success_msg = f"Docker image built successfully: {image_name}:{tag}"
                logger.info(success_msg)
                return True, success_msg
            else:
                error_msg = f"Failed to build Docker image.\nStdout: {stdout}\nStderr: {stderr}"
                logger.error(error_msg)
                return False, error_msg
                
        except Exception as e:
            error_msg = f"Error building Docker image: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def run_container(self, 
                     image_name: str,
                     container_name: str,
                     port_mapping: Dict[int, int],
                     env_vars: Dict[str, str] = None,
                     detached: bool = True,
                     restart_policy: str = 'unless-stopped') -> Tuple[bool, str]:
        """
        Run Docker container from image.
        
        Args:
            image_name: Docker image name with tag
            container_name: Name for the container
            port_mapping: Dictionary of {host_port: container_port}
            env_vars: Environment variables for the container
            detached: Run container in detached mode
            restart_policy: Container restart policy
            
        Returns:
            Tuple of (success, message)
        """
        try:
            logger.info(f"Running Docker container: {container_name}")
            
            # Build docker run command
            run_command = f"sudo docker run"
            
            if detached:
                run_command += " -d"
            
            # Add restart policy
            run_command += f" --restart {restart_policy}"
            
            # Add container name
            run_command += f" --name {container_name}"
            
            # Add port mappings
            for host_port, container_port in port_mapping.items():
                run_command += f" -p {host_port}:{container_port}"
            
            # Add environment variables
            if env_vars:
                for key, value in env_vars.items():
                    run_command += f' -e {key}="{value}"'
            
            # Add image name
            run_command += f" {image_name}"
            
            logger.info(f"Docker run command: {run_command}")
            
            exit_code, stdout, stderr = self.ssh.execute_command(run_command)
            
            if exit_code == 0:
                container_id = stdout.strip()
                success_msg = f"Container started successfully: {container_id[:12]}"
                logger.info(success_msg)
                return True, success_msg
            else:
                error_msg = f"Failed to start container.\nStdout: {stdout}\nStderr: {stderr}"
                logger.error(error_msg)
                return False, error_msg
                
        except Exception as e:
            error_msg = f"Error running container: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def get_container_status(self, container_name: str) -> Dict:
        """
        Get status of a Docker container.
        
        Args:
            container_name: Container name
            
        Returns:
            Dictionary with container status
        """
        try:
            command = f"sudo docker inspect {container_name}"
            exit_code, stdout, stderr = self.ssh.execute_command(command)
            
            if exit_code == 0:
                import json
                container_info = json.loads(stdout)[0]
                
                return {
                    'name': container_info['Name'].lstrip('/'),
                    'status': container_info['State']['Status'],
                    'running': container_info['State']['Running'],
                    'started_at': container_info['State']['StartedAt'],
                    'image': container_info['Config']['Image']
                }
            else:
                return {'status': 'not_found', 'running': False}
                
        except Exception as e:
            logger.error(f"Error getting container status: {str(e)}")
            return {'status': 'error', 'running': False, 'error': str(e)}
    
    def stop_container(self, container_name: str) -> Tuple[bool, str]:
        """
        Stop a running container.
        
        Args:
            container_name: Container name
            
        Returns:
            Tuple of (success, message)
        """
        try:
            logger.info(f"Stopping container: {container_name}")
            
            command = f"sudo docker stop {container_name}"
            exit_code, stdout, stderr = self.ssh.execute_command(command)
            
            if exit_code == 0:
                return True, f"Container {container_name} stopped successfully"
            else:
                return False, f"Failed to stop container: {stderr}"
                
        except Exception as e:
            return False, f"Error stopping container: {str(e)}"
    
    def remove_container(self, container_name: str, force: bool = False) -> Tuple[bool, str]:
        """
        Remove a container.
        
        Args:
            container_name: Container name
            force: Force remove running container
            
        Returns:
            Tuple of (success, message)
        """
        try:
            logger.info(f"Removing container: {container_name}")
            
            command = f"sudo docker rm {'-f ' if force else ''}{container_name}"
            exit_code, stdout, stderr = self.ssh.execute_command(command)
            
            if exit_code == 0:
                return True, f"Container {container_name} removed successfully"
            else:
                return False, f"Failed to remove container: {stderr}"
                
        except Exception as e:
            return False, f"Error removing container: {str(e)}"
    
    def get_container_logs(self, container_name: str, tail: int = 100) -> str:
        """
        Get logs from a container.
        
        Args:
            container_name: Container name
            tail: Number of lines to retrieve
            
        Returns:
            Container logs
        """
        try:
            command = f"sudo docker logs --tail {tail} {container_name}"
            exit_code, stdout, stderr = self.ssh.execute_command(command)
            
            return stdout + stderr
            
        except Exception as e:
            logger.error(f"Error getting container logs: {str(e)}")
            return f"Error: {str(e)}"
    
    def list_containers(self, all_containers: bool = False) -> List[Dict]:
        """
        List Docker containers.
        
        Args:
            all_containers: Include stopped containers
            
        Returns:
            List of container information
        """
        try:
            command = f"sudo docker ps {'-a' if all_containers else ''} --format '{{{{json .}}}}'"
            exit_code, stdout, stderr = self.ssh.execute_command(command)
            
            if exit_code == 0:
                import json
                containers = []
                for line in stdout.strip().split('\n'):
                    if line:
                        containers.append(json.loads(line))
                return containers
            else:
                return []
                
        except Exception as e:
            logger.error(f"Error listing containers: {str(e)}")
            return []
    
    def close(self):
        """Close SSH connection."""
        self.ssh.close()
