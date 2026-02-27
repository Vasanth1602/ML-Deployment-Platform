"""
Deployment Orchestrator for the Automated Deployment Framework.
Coordinates the entire deployment workflow from GitHub to deployed application.

Phase 3 changes:
  - Every deployment is now persisted to the database (no more in-memory dict)
  - Uses the Repository pattern — all DB operations go through repositories.py
  - list_deployments() and get_deployment_status() query the DB, not memory
  - Survives server restarts: deployments are durable
"""

import logging
import time
import uuid
from typing import Dict, Optional, Callable
from datetime import datetime

from ..providers.aws.aws_manager import AWSManager
from ..providers.docker.docker_manager import DockerManager
from ..providers.github.github_manager import GitHubManager
from ..providers.nginx.nginx_manager import NginxManager
from ..services.health_checker import HealthChecker
from ..core.logging_config import set_deployment_context, clear_deployment_context
from ..core.input_validators import validate_github_url, validate_deployment_config
from ..core.utils import sanitize_name, format_deployment_url, parse_github_url
from ..config import config

# ── Database imports ──────────────────────────────────────────────────────────
from ..database.connection import SessionLocal
from ..database.repositories import (
    TenantRepository,
    ApplicationRepository,
    EC2InstanceRepository,
    DeploymentRepository,
)

logger = logging.getLogger(__name__)


class DeploymentOrchestrator:
    """Orchestrates the complete deployment workflow."""

    def __init__(self):
        """Initialize Deployment Orchestrator."""
        self.aws_manager = AWSManager()
        # ── NOTE: self.deployments dict is GONE ──────────────────────────────
        # All state now lives in the database. Use list_deployments() and
        # get_deployment_status() which query the DB.

    # ─────────────────────────────────────────────────────────────────────────
    # Main deploy() method
    # ─────────────────────────────────────────────────────────────────────────
    def deploy(self,
               github_url: str,
               instance_name: Optional[str] = None,
               container_port: int = None,
               host_port: int = None,
               progress_callback: Optional[Callable] = None) -> Dict:
        """
        Execute complete deployment workflow.

        Args:
            github_url:        GitHub repository URL
            instance_name:     Custom instance name (auto-generated if None)
            container_port:    Container port (uses config default if None)
            host_port:         Host port (uses config default if None)
            progress_callback: Function called for real-time WebSocket updates

        Returns:
            Dictionary with deployment results (always returned, even on failure)
        """
        # ── Open a dedicated DB session for this deployment ──────────────────
        # Deployment runs in a background thread, so it needs its own session
        # (it can't share the Flask request-scoped session).
        db = SessionLocal()
        dep_repo   = DeploymentRepository(db)
        tenant_repo = TenantRepository(db)
        app_repo   = ApplicationRepository(db)
        ec2_repo   = EC2InstanceRepository(db)

        # Build a result dict (same shape as the old in-memory version)
        result = {
            'deployment_id': None,   # filled once Deployment row is created
            'success': False,
            'github_url': github_url,
            'start_time': datetime.now().isoformat(),
            'steps': [],
        }

        dep = None   # Deployment ORM object — used in except block too

        try:
            # ── Resolve tenant (single-tenant: always 'default') ─────────────
            tenant = tenant_repo.get_default()
            if not tenant:
                raise RuntimeError(
                    "No default tenant found. Run 'flask init-db' or restart Flask.")

            # ── Helper: emit progress + write to DB log ──────────────────────
            def update_progress(step: str, message: str,
                                status: str = 'in_progress', data: dict = None):
                if status == 'error':
                    logger.error(f"[{status.upper()}] {step}: {message}")
                else:
                    logger.info(f"[{status.upper()}] {step}: {message}")
                    
                result['steps'].append({
                    'step': step,
                    'message': message,
                    'status': status,
                    'timestamp': datetime.now().isoformat(),
                })
                # Write to DB log if we have a deployment record
                if dep:
                    dep_repo.add_log(dep.id, f"[{step}] {message}",
                                     level='ERROR' if status == 'error' else 'INFO')
                    db.commit()

                if progress_callback:
                    progress_callback(step, message, status, data)

            # ── Step 1: Validate GitHub URL ───────────────────────────────────
            update_progress('Validation', 'Validating GitHub URL', 'in_progress')
            is_valid, error = validate_github_url(github_url)
            if not is_valid:
                raise ValueError(f"Invalid GitHub URL: {error}")
            update_progress('Validation', 'GitHub URL validated', 'success')

            # ── Step 2: Validate config ───────────────────────────────────────
            update_progress('Validation', 'Validating configuration', 'in_progress')
            deploy_cfg = {
                'github_url': github_url,
                'port': host_port or config.DOCKER_HOST_PORT,
            }
            is_valid, errors = validate_deployment_config(deploy_cfg)
            if not is_valid:
                raise ValueError(f"Invalid configuration: {', '.join(errors)}")
            update_progress('Validation', 'Configuration validated', 'success')

            # ── Step 2.5: Resolve/create Application record ───────────────────
            _, repo_name = parse_github_url(github_url)
            app_name = sanitize_name(repo_name)

            application = app_repo.get_or_create(
                tenant_id=tenant.id,
                name=app_name,
                github_url=github_url,
                container_port=container_port or config.DOCKER_CONTAINER_PORT,
                repo_name=repo_name,
                branch='main',
                status='pending',
            )
            db.commit()

            # ── Step 2.6: Create Deployment record in DB ──────────────────────
            dep = dep_repo.create(
                tenant_id=tenant.id,
                application_id=application.id,
            )
            db.commit()

            # Now we have a real deployment ID — update result + ContextVar
            result['deployment_id'] = dep.short_id
            set_deployment_context(dep.short_id)
            logger.info('Deployment record created: short_id=%s (db_id=%s...)',
                        dep.short_id, dep.id[:8])

            # ── Step 3: Create EC2 instance ───────────────────────────────────
            update_progress('EC2 Creation', 'Creating EC2 instance', 'in_progress')

            if instance_name is None:
                instance_name = f"autodeploy-{sanitize_name(repo_name)}-{dep.short_id}"

            instance_info = self.aws_manager.create_instance(instance_name)
            result['instance_id'] = instance_info['instance_id']
            result['public_ip']   = instance_info['public_ip']

            # Persist EC2 instance to DB
            ec2_record = ec2_repo.create(
                aws_instance_id=instance_info['instance_id'],
                public_ip=instance_info['public_ip'],
                instance_type=instance_info.get('instance_type', config.EC2_INSTANCE_TYPE),
                region=config.AWS_REGION,
            )
            # Link application → instance
            ec2_repo.link_application(
                app_id=application.id,
                instance_db_id=ec2_record.id,
                host_port=host_port or config.DOCKER_HOST_PORT,
            )
            dep_repo.add_step(dep.id, 1, 'EC2 Instance Created', 'success',
                              message=f"id={instance_info['instance_id']} ip={instance_info['public_ip']}")
            db.commit()

            update_progress('EC2 Creation',
                           f"Instance {instance_info['instance_id']} created",
                           'success', {'public_ip': instance_info['public_ip']})

            # ── Step 4: SSH + Docker ──────────────────────────────────────────
            update_progress('Docker Installation',
                           'Waiting for SSH and installing Docker', 'in_progress')

            docker_manager = DockerManager(
                instance_info['public_ip'],
                key_file=f"{config.AWS_KEY_PAIR_NAME}.pem"
            )
            try:
                docker_manager.connect(max_wait=180, retry_interval=5,
                                       progress_callback=progress_callback)
            except TimeoutError as e:
                raise Exception(f"SSH connection timeout: {e}")
            except Exception as e:
                raise Exception(f"Failed to establish SSH connection: {e}")

            docker_installed, docker_msg = docker_manager.install_docker()
            if not docker_installed:
                raise Exception(f"Failed to install Docker: {docker_msg}")

            dep_repo.add_step(dep.id, 2, 'Docker Installed', 'success')
            db.commit()
            update_progress('Docker Installation', 'Docker installed', 'success')

            # ── Step 4.5: NGINX (optional) ────────────────────────────────────
            nginx_manager = None
            if config.ENABLE_NGINX:
                update_progress('NGINX Installation',
                               'Installing NGINX reverse proxy', 'in_progress')
                nginx_manager = NginxManager(
                    instance_info['public_ip'],
                    key_file=f"{config.AWS_KEY_PAIR_NAME}.pem"
                )
                try:
                    nginx_manager.connect(max_wait=180, retry_interval=5,
                                          progress_callback=progress_callback)
                except Exception as e:
                    raise Exception(f"SSH for NGINX failed: {e}")

                nginx_installed, nginx_msg = nginx_manager.install_nginx()
                if not nginx_installed:
                    raise Exception(f"Failed to install NGINX: {nginx_msg}")

                dep_repo.add_step(dep.id, 3, 'NGINX Installed', 'success')
                db.commit()
                update_progress('NGINX Installation', 'NGINX installed', 'success')

            # ── Step 5: Clone repository ──────────────────────────────────────
            update_progress('Repository Clone', 'Cloning GitHub repository', 'in_progress')

            github_manager = GitHubManager(
                instance_info['public_ip'],
                key_file=f"{config.AWS_KEY_PAIR_NAME}.pem"
            )
            try:
                github_manager.connect(max_wait=180, retry_interval=5,
                                       progress_callback=progress_callback)
            except Exception as e:
                raise Exception(f"SSH for GitHub failed: {e}")

            clone_success, clone_msg, repo_path = github_manager.clone_repository(
                github_url, token=config.GITHUB_TOKEN)

            if not clone_success:
                raise Exception(f"Failed to clone repository: {clone_msg}")

            result['repo_path'] = repo_path

            dep_repo.add_step(dep.id, 4, 'Repository Cloned', 'success',
                              message=repo_path)
            db.commit()
            update_progress('Repository Clone', f"Cloned to {repo_path}", 'success')

            # ── Step 6: Verify project files ─────────────────────────────────
            update_progress('Project Validation', 'Verifying project structure', 'in_progress')

            files_exist, missing_files = github_manager.verify_project_files(repo_path)
            if not files_exist:
                raise Exception(f"Missing required files: {', '.join(missing_files)}")

            dep_repo.add_step(dep.id, 5, 'Project Structure Verified', 'success')
            db.commit()
            update_progress('Project Validation', 'Project structure validated', 'success')

            # ── Step 7: Build Docker image ────────────────────────────────────
            update_progress('Docker Build', 'Building Docker image', 'in_progress')

            image_name = sanitize_name(instance_name)
            build_success, build_msg = docker_manager.build_image(repo_path, image_name)

            if not build_success:
                raise Exception(f"Failed to build Docker image: {build_msg}")

            result['image_name'] = image_name
            dep_repo.add_step(dep.id, 6, 'Docker Image Built', 'success',
                              message=image_name)
            db.commit()
            update_progress('Docker Build', f"Image built: {image_name}", 'success')

            # ── Step 8: Run container ─────────────────────────────────────────
            update_progress('Container Deployment', 'Starting Docker container', 'in_progress')

            container_name  = f"{image_name}-container"
            container_port  = container_port or config.DOCKER_CONTAINER_PORT
            host_port       = host_port or config.DOCKER_HOST_PORT
            port_mapping    = {host_port: container_port}

            run_success, run_msg = docker_manager.run_container(
                f"{image_name}:latest",
                container_name,
                port_mapping,
                restart_policy='unless-stopped',
            )

            if not run_success:
                raise Exception(f"Failed to start container: {run_msg}")

            result['container_name'] = container_name
            result['port'] = host_port

            # Update Application record with container details
            db.query(application.__class__).filter_by(id=application.id).update({
                'container_name': container_name,
                'image_name': image_name,
                'status': 'active',
                'updated_at': datetime.utcnow(),
            })
            dep_repo.add_step(dep.id, 7, 'Container Started', 'success',
                              message=container_name)
            db.commit()
            update_progress('Container Deployment',
                           f"Container running: {container_name}", 'success')

            # ── Step 8.5: Configure NGINX ─────────────────────────────────────
            if config.ENABLE_NGINX and nginx_manager:
                update_progress('NGINX Configuration',
                               'Configuring NGINX reverse proxy', 'in_progress')

                cfg_ok, cfg_msg = nginx_manager.create_site_config(
                    app_name=instance_name,
                    proxy_port=host_port,
                    server_name='_',
                )
                if not cfg_ok:
                    raise Exception(f"NGINX config failed: {cfg_msg}")

                en_ok, en_msg = nginx_manager.enable_site(instance_name)
                if not en_ok:
                    raise Exception(f"NGINX enable failed: {en_msg}")

                rl_ok, rl_msg = nginx_manager.reload_nginx()
                if not rl_ok:
                    raise Exception(f"NGINX reload failed: {rl_msg}")

                dep_repo.add_step(dep.id, 8, 'NGINX Configured', 'success')
                db.commit()
                update_progress('NGINX Configuration', 'NGINX configured', 'success')
                health_check_port = 80
            else:
                health_check_port = host_port

            # ── Step 9: Health check ──────────────────────────────────────────
            update_progress('Health Check', 'Performing health checks', 'in_progress')

            health_checker = HealthChecker(instance_info['public_ip'], health_check_port)
            is_healthy, health_msg = health_checker.wait_for_healthy(
                max_retries=config.HEALTH_CHECK_RETRIES,
                retry_interval=config.HEALTH_CHECK_INTERVAL,
            )

            if is_healthy:
                dep_repo.add_step(dep.id, 9, 'Health Check Passed', 'success')
                update_progress('Health Check', 'Application is healthy', 'success')
            else:
                dep_repo.add_step(dep.id, 9, 'Health Check Warning', 'warning',
                                  message=health_msg)
                update_progress('Health Check',
                               f"Health check warning: {health_msg}", 'warning')
            db.commit()

            # ── Step 10: Finalize ─────────────────────────────────────────────
            deployment_url = (
                f"http://{instance_info['public_ip']}/"
                if config.ENABLE_NGINX
                else format_deployment_url(instance_info['public_ip'], host_port)
            )

            result['url']           = deployment_url
            result['nginx_enabled'] = config.ENABLE_NGINX
            result['success']       = True
            result['end_time']      = datetime.now().isoformat()

            # Persist success + URL to DB
            dep_repo.mark_success(dep.id, deployment_url)
            app_repo.update_last_deployed(application.id)
            db.commit()

            # Close SSH connections
            docker_manager.close()
            github_manager.close()
            if nginx_manager:
                nginx_manager.close()

            update_progress('Deployment Complete',
                           'Application deployed successfully', 'success',
                           {'url': deployment_url})

            logger.info('[OK] Deployment %s completed: %s', dep.short_id, deployment_url)
            return result

        # ─────────────────────────────────────────────────────────────────────
        # Failure path
        # ─────────────────────────────────────────────────────────────────────
        except Exception as e:
            error_msg = str(e)
            logger.error('[ERROR] Deployment failed: %s', error_msg)

            result['success']  = False
            result['error']    = error_msg
            result['end_time'] = datetime.now().isoformat()

            try:
                db.rollback()   # discard any uncommitted buffered writes
                if dep:
                    dep_repo.mark_failed(dep.id, error_msg)
                    db.commit()
            except Exception as db_err:
                logger.error('DB error while recording failure: %s', db_err)

            # Attempt EC2 cleanup
            if 'instance_id' in result:
                try:
                    update_progress('Cleanup', 'Cleaning up failed deployment', 'in_progress')
                    # Uncomment below to auto-terminate on failure:
                    # self.aws_manager.terminate_instance(result['instance_id'])
                    update_progress('Cleanup', 'Cleanup noted (instance kept for debugging)', 'success')
                except Exception as cleanup_err:
                    logger.error('Cleanup failed: %s', cleanup_err)

            return result

        finally:
            clear_deployment_context()
            db.close()   # always return connection to pool

    # ─────────────────────────────────────────────────────────────────────────
    # Query methods — now read from DB instead of in-memory dict
    # ─────────────────────────────────────────────────────────────────────────
    def get_deployment_status(self, deployment_id: str) -> Optional[Dict]:
        """
        Get status of a deployment by short_id or full UUID.
        Returns None if not found.
        """
        db = SessionLocal()
        try:
            repo = DeploymentRepository(db)
            # Try short_id first (8 chars), then full UUID
            if len(deployment_id) == 8:
                dep = repo.get_by_short_id(deployment_id)
            else:
                dep = repo.get_by_id(deployment_id)

            if not dep:
                return None

            return {
                'deployment_id': dep.short_id,
                'status':        dep.status,
                'github_url':    dep.application.github_url if dep.application else None,
                'url':           dep.deployment_url,
                'error':         dep.error_message,
                'start_time':    dep.started_at.isoformat() if dep.started_at else None,
                'end_time':      dep.completed_at.isoformat() if dep.completed_at else None,
                'duration_seconds': dep.duration_seconds,
                'steps': [
                    {
                        'step_number': s.step_number,
                        'step_name':   s.step_name,
                        'status':      s.status,
                        'message':     s.message,
                    }
                    for s in dep.steps
                ],
            }
        finally:
            db.close()

    def list_deployments(self) -> list:
        """
        List all deployments from the database (most recent first).
        Returns same shape as before for API backward-compatibility.
        """
        db = SessionLocal()
        try:
            repo = DeploymentRepository(db)
            deps = repo.list_all(limit=50)
            return [
                {
                    'deployment_id': d.short_id,
                    'github_url':    d.application.github_url if d.application else None,
                    'success':       d.status == 'success',
                    'status':        d.status,
                    'url':           d.deployment_url,
                    'start_time':    d.started_at.isoformat() if d.started_at else None,
                    'duration_seconds': d.duration_seconds,
                }
                for d in deps
            ]
        finally:
            db.close()
