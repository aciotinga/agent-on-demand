"""Docker client for container lifecycle management."""

import docker
from docker.errors import DockerException, ImageNotFound, ContainerError
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging
import time

logger = logging.getLogger(__name__)


class DockerClient:
    """Manages Docker container operations for capsules."""
    
    def __init__(self, network_name: str = "aod-network"):
        """Initialize Docker client.
        
        Args:
            network_name: Name of the Docker network to use/create.
        """
        try:
            self.client = docker.from_env()
            self.network_name = network_name
            self._ensure_network()
        except DockerException as e:
            logger.error(f"Failed to initialize Docker client: {e}")
            raise
    
    def _ensure_network(self):
        """Ensure the Docker network exists, create if it doesn't."""
        try:
            networks = self.client.networks.list(names=[self.network_name])
            if not networks:
                logger.info(f"Creating Docker network: {self.network_name}")
                self.client.networks.create(
                    self.network_name,
                    driver="bridge",
                    check_duplicate=True
                )
            else:
                logger.debug(f"Docker network {self.network_name} already exists")
        except Exception as e:
            logger.warning(f"Could not ensure network exists: {e}")
    
    def build_capsule(self, image_name: str, capsule_path: str, tag: Optional[str] = None) -> bool:
        """Build Docker image from capsule directory.
        
        Args:
            image_name: Name for the Docker image.
            capsule_path: Path to the capsule directory containing Dockerfile.
            tag: Optional tag for the image. Defaults to 'latest'.
            
        Returns:
            True if successful, False otherwise.
        """
        if tag is None:
            tag = "latest"
        
        full_image_name = f"{image_name}:{tag}"
        capsule_dir = Path(capsule_path)
        
        if not capsule_dir.exists():
            logger.error(f"Capsule path does not exist: {capsule_path}")
            return False
        
        dockerfile_path = capsule_dir / "Dockerfile"
        if not dockerfile_path.exists():
            logger.error(f"Dockerfile not found: {dockerfile_path}")
            return False
        
        try:
            logger.info(f"Building Docker image: {full_image_name} from {capsule_path}")
            image, build_logs = self.client.images.build(
                path=str(capsule_dir),
                tag=full_image_name,
                rm=True,
                forcerm=True
            )
            
            # Log build output
            for log in build_logs:
                if 'stream' in log:
                    logger.debug(log['stream'].strip())
                elif 'error' in log:
                    logger.error(f"Build error: {log['error']}")
            
            logger.info(f"Successfully built image: {full_image_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to build Docker image: {e}")
            return False
    
    def run_capsule(
        self,
        image_name: str,
        volume_mounts: Dict[str, Dict[str, str]],
        env_vars: Optional[Dict[str, str]] = None,
        container_name: Optional[str] = None,
        tag: str = "latest"
    ) -> Optional[str]:
        """Run a capsule container.
        
        Args:
            image_name: Name of the Docker image.
            volume_mounts: Dictionary mapping container paths to host paths.
                          Format: {"/io": {"bind": "/host/path", "mode": "rw"}}
            env_vars: Optional environment variables to set.
            container_name: Optional name for the container.
            tag: Image tag. Defaults to 'latest'.
            
        Returns:
            Container ID if successful, None otherwise.
        """
        full_image_name = f"{image_name}:{tag}"
        
        # Check if image exists
        try:
            self.client.images.get(full_image_name)
        except ImageNotFound:
            logger.error(f"Image not found: {full_image_name}")
            return None
        
        # Prepare volume mounts in Docker format
        binds = {}
        for container_path, mount_info in volume_mounts.items():
            host_path = mount_info.get("bind")
            mode = mount_info.get("mode", "rw")
            if host_path:
                binds[host_path] = {"bind": container_path, "mode": mode}
        
        try:
            logger.info(f"Running container from image: {full_image_name}")
            container = self.client.containers.run(
                full_image_name,
                detach=True,
                volumes=binds,
                environment=env_vars,
                name=container_name,
                network=self.network_name,
                remove=False,  # We'll remove manually after retrieving output
                auto_remove=False
            )
            
            logger.info(f"Container started: {container.id[:12]}")
            return container.id
        except ContainerError as e:
            logger.error(f"Container error: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to run container: {e}")
            return None
    
    def wait_for_container(self, container_id: str, timeout: Optional[int] = None) -> Optional[int]:
        """Wait for a container to finish and return its exit code.
        
        Args:
            container_id: Container ID.
            timeout: Optional timeout in seconds.
            
        Returns:
            Exit code if successful, None on error or timeout.
        """
        try:
            container = self.client.containers.get(container_id)
            exit_result = container.wait(timeout=timeout)
            # Docker wait() returns a dict like {"StatusCode": 0}, extract the integer
            if isinstance(exit_result, dict):
                exit_code = exit_result.get("StatusCode", -1)
            else:
                exit_code = exit_result
            logger.debug(f"Container {container_id[:12]} exited with code: {exit_code}")
            return exit_code
        except Exception as e:
            logger.error(f"Error waiting for container: {e}")
            return None
    
    def get_container_logs(self, container_id: str, tail: int = 100) -> str:
        """Get logs from a container.
        
        Args:
            container_id: Container ID.
            tail: Number of log lines to retrieve.
            
        Returns:
            Log output as string.
        """
        try:
            container = self.client.containers.get(container_id)
            # Get all logs, not just tail, to ensure we capture errors
            logs = container.logs(stdout=True, stderr=True)
            return logs.decode('utf-8', errors='replace')
        except Exception as e:
            logger.error(f"Error getting container logs: {e}")
            return ""
    
    def stop_capsule(self, container_id: str, timeout: int = 10) -> bool:
        """Stop a running container.
        
        Args:
            container_id: Container ID.
            timeout: Timeout in seconds before force kill.
            
        Returns:
            True if successful, False otherwise.
        """
        try:
            container = self.client.containers.get(container_id)
            container.stop(timeout=timeout)
            logger.info(f"Stopped container: {container_id[:12]}")
            return True
        except Exception as e:
            logger.error(f"Failed to stop container: {e}")
            return False
    
    def remove_capsule(self, container_id: str, force: bool = False) -> bool:
        """Remove a container.
        
        Args:
            container_id: Container ID.
            force: Force removal if container is running.
            
        Returns:
            True if successful, False otherwise.
        """
        try:
            container = self.client.containers.get(container_id)
            container.remove(force=force)
            logger.info(f"Removed container: {container_id[:12]}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove container: {e}")
            return False
    
    def container_exists(self, container_id: str) -> bool:
        """Check if a container exists.
        
        Args:
            container_id: Container ID.
            
        Returns:
            True if container exists, False otherwise.
        """
        try:
            self.client.containers.get(container_id)
            return True
        except Exception:
            return False
    
    def is_container_running(self, container_id: str) -> bool:
        """Check if a container is currently running.
        
        Args:
            container_id: Container ID.
            
        Returns:
            True if container is running, False otherwise.
        """
        try:
            container = self.client.containers.get(container_id)
            container.reload()
            return container.status == "running"
        except Exception:
            return False
