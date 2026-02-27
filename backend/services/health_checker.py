"""
Health Checker for the Automated Deployment Framework.
Monitors container and application health.
"""

import logging
import time
import requests
from typing import Dict, Optional, Tuple
from ..core.utils import check_url_health

logger = logging.getLogger(__name__)


class HealthChecker:
    """Monitors health of deployed applications."""
    
    def __init__(self, public_ip: str, port: int, protocol: str = 'http'):
        """
        Initialize Health Checker.
        
        Args:
            public_ip: Public IP of the EC2 instance
            port: Application port
            protocol: Protocol (http or https)
        """
        self.public_ip = public_ip
        self.port = port
        self.protocol = protocol
        self.base_url = f"{protocol}://{public_ip}:{port}"
    
    def check_container_health(self, docker_manager, container_name: str) -> Tuple[bool, Dict]:
        """
        Check Docker container health.
        
        Args:
            docker_manager: DockerManager instance
            container_name: Container name
            
        Returns:
            Tuple of (is_healthy, status_dict)
        """
        try:
            status = docker_manager.get_container_status(container_name)
            
            is_healthy = status.get('running', False)
            
            return is_healthy, status
            
        except Exception as e:
            logger.error(f"Error checking container health: {str(e)}")
            return False, {'error': str(e)}
    
    def check_application_health(self, 
                                endpoint: str = '/',
                                timeout: int = 10,
                                expected_status: int = 200) -> Tuple[bool, Dict]:
        """
        Check application health via HTTP request.
        
        Args:
            endpoint: Health check endpoint
            timeout: Request timeout in seconds
            expected_status: Expected HTTP status code
            
        Returns:
            Tuple of (is_healthy, response_dict)
        """
        try:
            url = f"{self.base_url}{endpoint}"
            logger.info(f"Checking application health: {url}")
            
            start_time = time.time()
            response = requests.get(url, timeout=timeout)
            response_time = time.time() - start_time
            
            is_healthy = response.status_code == expected_status
            
            result = {
                'url': url,
                'status_code': response.status_code,
                'response_time': round(response_time, 3),
                'healthy': is_healthy
            }
            
            if is_healthy:
                logger.info(f"Application is healthy (status: {response.status_code}, time: {response_time:.3f}s)")
            else:
                logger.warning(f"Application health check failed (status: {response.status_code})")
            
            return is_healthy, result
            
        except requests.exceptions.Timeout:
            logger.error(f"Health check timed out after {timeout}s")
            return False, {'error': 'timeout', 'timeout': timeout}
        except requests.exceptions.ConnectionError:
            logger.error("Failed to connect to application")
            return False, {'error': 'connection_error'}
        except Exception as e:
            logger.error(f"Error checking application health: {str(e)}")
            return False, {'error': str(e)}
    
    def wait_for_healthy(self, 
                        max_retries: int = 10,
                        retry_interval: int = 10,
                        endpoint: str = '/') -> Tuple[bool, str]:
        """
        Wait for application to become healthy.
        
        Args:
            max_retries: Maximum number of health check attempts
            retry_interval: Time between retries in seconds
            endpoint: Health check endpoint
            
        Returns:
            Tuple of (is_healthy, message)
        """
        logger.info(f"Waiting for application to become healthy (max {max_retries} attempts)")
        
        for attempt in range(1, max_retries + 1):
            logger.info(f"Health check attempt {attempt}/{max_retries}")
            
            is_healthy, result = self.check_application_health(endpoint)
            
            if is_healthy:
                success_msg = f"Application is healthy after {attempt} attempts"
                logger.info(success_msg)
                return True, success_msg
            
            if attempt < max_retries:
                logger.info(f"Application not ready, waiting {retry_interval}s before retry...")
                time.sleep(retry_interval)
        
        error_msg = f"Application failed to become healthy after {max_retries} attempts"
        logger.error(error_msg)
        return False, error_msg
    
    def comprehensive_health_check(self, 
                                  docker_manager,
                                  container_name: str,
                                  endpoint: str = '/') -> Dict:
        """
        Perform comprehensive health check (container + application).
        
        Args:
            docker_manager: DockerManager instance
            container_name: Container name
            endpoint: Application health check endpoint
            
        Returns:
            Dictionary with complete health status
        """
        logger.info("Performing comprehensive health check")
        
        # Check container health
        container_healthy, container_status = self.check_container_health(docker_manager, container_name)
        
        # Check application health
        app_healthy, app_status = self.check_application_health(endpoint)
        
        overall_healthy = container_healthy and app_healthy
        
        result = {
            'overall_healthy': overall_healthy,
            'container': {
                'healthy': container_healthy,
                'status': container_status
            },
            'application': {
                'healthy': app_healthy,
                'status': app_status
            },
            'timestamp': time.time()
        }
        
        if overall_healthy:
            logger.info("[OK] Comprehensive health check passed")
        else:
            logger.warning("[FAILED] Comprehensive health check failed")
        
        return result
