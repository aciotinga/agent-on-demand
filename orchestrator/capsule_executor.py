"""Capsule execution logic - handles full lifecycle of capsule execution."""

import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

from .docker_client import DockerClient
from .file_manager import FileManager
from .utils.volume_manager import VolumeManager
from .utils.schema_validator import SchemaValidator
from .exceptions import CapsuleNotFoundError, SchemaValidationError, DockerOperationError, FileOperationError

logger = logging.getLogger(__name__)


class CapsuleExecutor:
    """Executes capsules with full lifecycle management."""
    
    def __init__(
        self,
        docker_client: DockerClient,
        file_manager: FileManager,
        volume_manager: VolumeManager,
        config
    ):
        """Initialize capsule executor.
        
        Args:
            docker_client: DockerClient instance.
            file_manager: FileManager instance.
            volume_manager: VolumeManager instance.
            config: Config instance with capsule registry.
        """
        self.docker_client = docker_client
        self.file_manager = file_manager
        self.volume_manager = volume_manager
        self.config = config
        self.state_tracker = None
    
    def set_state_tracker(self, state_tracker):
        """Set the state tracker for monitoring.
        
        Args:
            state_tracker: StateTracker instance.
        """
        self.state_tracker = state_tracker
    
    def execute_capsule(
        self,
        capsule_name: str,
        input_data: Dict[str, Any],
        input_files: Optional[Dict[str, str]] = None,
        session_id: Optional[str] = None,
        orchestrator_url: Optional[str] = None,
        parent_session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute a capsule with full lifecycle management.
        
        Args:
            capsule_name: Name of the capsule to execute.
            input_data: Input data dictionary (primitives and file references).
            input_files: Optional dict mapping filenames to source file paths.
            session_id: Optional session ID. If None, generates a new one.
            orchestrator_url: Optional orchestrator URL for handoff requests.
            
        Returns:
            Dictionary with 'success', 'output', 'files', and 'error' keys.
        """
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        # Register execution with state tracker
        if self.state_tracker:
            self.state_tracker.register_execution(
                session_id=session_id,
                capsule_name=capsule_name,
                parent_session_id=parent_session_id
            )
        
        # Get capsule configuration
        capsule_config = self.config.get_capsule(capsule_name)
        if not capsule_config:
            error_msg = f"Capsule '{capsule_name}' not found in registry"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
        
        capsule_path = capsule_config['path']
        image_name = capsule_config['image']
        
        # Validate input schema
        try:
            validator = SchemaValidator(capsule_path)
            is_valid, error_msg = validator.validate_input(input_data)
            if not is_valid:
                logger.error(f"Input validation failed for {capsule_name}: {error_msg}")
                return {
                    "success": False,
                    "error": f"Input validation failed: {error_msg}"
                }
        except Exception as e:
            logger.error(f"Error during schema validation: {e}")
            return {
                "success": False,
                "error": f"Schema validation error: {str(e)}"
            }
        
        try:
            # Create session volume
            volume_path = self.volume_manager.create_session_volume(session_id)
            logger.info(f"Created session volume: {volume_path} for capsule: {capsule_name}")
            
            # Copy input files if provided
            if input_files:
                for filename, source_path in input_files.items():
                    try:
                        if not self.file_manager.copy_to_input(source_path, session_id, filename):
                            error_msg = f"Failed to copy input file: {filename}"
                            logger.error(error_msg)
                            return {
                                "success": False,
                                "error": error_msg
                            }
                    except Exception as e:
                        error_msg = f"Error copying input file {filename}: {str(e)}"
                        logger.error(error_msg)
                        return {
                            "success": False,
                            "error": error_msg
                        }
            
            # Detect and copy file paths in input_data (for 'file' and 'files' keys)
            # This allows capsules to accept file paths directly in input
            import os
            from pathlib import Path
            
            if 'file' in input_data and input_data['file']:
                file_path = input_data['file']
                if isinstance(file_path, str) and os.path.exists(file_path):
                    # It's a valid file path, copy it to /io/input/
                    filename = Path(file_path).name
                    if not self.file_manager.copy_to_input(file_path, session_id, filename):
                        error_msg = f"Failed to copy file from input: {file_path}"
                        logger.error(error_msg)
                        return {
                            "success": False,
                            "error": error_msg
                        }
                    # Update the path in input_data to point to /io/input/
                    input_data['file'] = f"/io/input/{filename}"
                    logger.debug(f"Copied file {file_path} to /io/input/{filename} and updated input")
            
            if 'files' in input_data and input_data['files']:
                files_list = input_data['files']
                if isinstance(files_list, list):
                    updated_files = []
                    for file_path in files_list:
                        if isinstance(file_path, str) and os.path.exists(file_path):
                            # It's a valid file path, copy it to /io/input/
                            filename = Path(file_path).name
                            if not self.file_manager.copy_to_input(file_path, session_id, filename):
                                error_msg = f"Failed to copy file from input: {file_path}"
                                logger.error(error_msg)
                                return {
                                    "success": False,
                                    "error": error_msg
                                }
                            # Update the path to point to /io/input/
                            updated_files.append(f"/io/input/{filename}")
                            logger.debug(f"Copied file {file_path} to /io/input/{filename}")
                        else:
                            # Keep the original path (might be a container path already)
                            updated_files.append(file_path)
                    input_data['files'] = updated_files
            
            # Write input JSON
            try:
                if not self.file_manager.write_input_json(session_id, input_data):
                    error_msg = "Failed to write input JSON"
                    logger.error(error_msg)
                    return {
                        "success": False,
                        "error": error_msg
                    }
            except Exception as e:
                error_msg = f"Error writing input JSON: {str(e)}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg
                }
            
            # Ensure Docker image is built
            if not self._ensure_image_built(image_name, capsule_path):
                return {
                    "success": False,
                    "error": f"Failed to build Docker image for capsule: {capsule_name}"
                }
            
            # Prepare volume mounts
            volume_mounts = {
                "/io": {
                    "bind": volume_path,
                    "mode": "rw"
                }
            }
            
            # Prepare environment variables
            env_vars = {}
            if orchestrator_url:
                env_vars["ORCHESTRATOR_URL"] = orchestrator_url
            
            # Add LLM API base URL for OpenAI-style API clients
            llm_api_base = self.config.get_llm_api_base()
            env_vars["OPENAI_API_BASE"] = llm_api_base
            # Also set as LITELLM_API_BASE for compatibility
            env_vars["LITELLM_API_BASE"] = llm_api_base
            
            # Add LLM API key (required by OpenAI client, can be dummy for LiteLLM proxy)
            llm_api_key = self.config.get_llm_api_key()
            env_vars["OPENAI_API_KEY"] = llm_api_key
            
            # Run container
            container_id = self.docker_client.run_capsule(
                image_name=image_name,
                volume_mounts=volume_mounts,
                env_vars=env_vars,
                container_name=f"aod-{session_id[:8]}"
            )
            
            if not container_id:
                if self.state_tracker:
                    self.state_tracker.update_execution_status(session_id, 'failed')
                return {
                    "success": False,
                    "error": "Failed to start container"
                }
            
            logger.info(f"Container started: {container_id[:12]}")
            
            # Update state tracker with container ID
            if self.state_tracker:
                self.state_tracker.update_execution_status(
                    session_id, 
                    'running', 
                    container_id=container_id
                )
            
            # Wait for container to complete
            exit_code = self.docker_client.wait_for_container(container_id, timeout=3600)
            
            if exit_code is None:
                # Timeout or error
                if self.state_tracker:
                    self.state_tracker.update_execution_status(session_id, 'failed')
                self.docker_client.stop_capsule(container_id)
                self.docker_client.remove_capsule(container_id, force=True)
                return {
                    "success": False,
                    "error": "Container execution timed out or failed"
                }
            
            # Get container logs for debugging (always show, not just on errors)
            logs = self.docker_client.get_container_logs(container_id)
            if logs:
                logger.info(f"[DEBUG] Container logs:\n{logs}")
            
            # Check exit code
            if exit_code != 0:
                if self.state_tracker:
                    self.state_tracker.update_execution_status(session_id, 'failed')
                self.docker_client.remove_capsule(container_id, force=True)
                error_msg = f"Container exited with code {exit_code}"
                if logs:
                    error_msg += f"\n\nContainer logs:\n{logs}"
                return {
                    "success": False,
                    "error": error_msg,
                    "logs": logs
                }
            
            # Read output JSON
            output_data = self.file_manager.read_output_json(session_id)
            if output_data is None:
                # Try to get logs for debugging
                return {
                    "success": False,
                    "error": "Failed to read output JSON",
                    "logs": logs
                }
            
            # Validate output schema
            is_valid, error_msg = validator.validate_output(output_data)
            if not is_valid:
                logger.warning(f"Output validation failed: {error_msg}")
                # Continue anyway, but log the warning
            
            # List output files
            output_files = self.file_manager.list_output_files(session_id)
            
            # Cleanup container
            self.docker_client.remove_capsule(container_id, force=True)
            
            # Update state tracker
            if self.state_tracker:
                self.state_tracker.update_execution_status(session_id, 'completed')
            
            return {
                "success": True,
                "output": output_data,
                "files": output_files,
                "session_id": session_id
            }
            
        except Exception as e:
            logger.error(f"Error executing capsule: {e}", exc_info=True)
            if self.state_tracker:
                self.state_tracker.update_execution_status(session_id, 'failed')
            return {
                "success": False,
                "error": str(e)
            }
        finally:
            # Clean up the session volume after execution completes
            # Handoffs create new sessions, so the original session can be cleaned up
            try:
                self.volume_manager.remove_session_volume(session_id)
                logger.debug(f"Cleaned up session volume: {session_id}")
            except Exception as e:
                logger.warning(f"Failed to clean up session volume {session_id}: {e}")
    
    def _ensure_image_built(self, image_name: str, capsule_path: str) -> bool:
        """Ensure Docker image is built, build if necessary.
        
        Args:
            image_name: Name of the Docker image.
            capsule_path: Path to capsule directory.
            
        Returns:
            True if image exists or was built successfully, False otherwise.
        """
        try:
            # Try to get the image
            self.docker_client.client.images.get(f"{image_name}:latest")
            logger.debug(f"Image {image_name}:latest already exists")
            return True
        except Exception:
            # Image doesn't exist, build it
            logger.info(f"Building image for {image_name}")
            return self.docker_client.build_capsule(image_name, capsule_path)
    
    def cleanup_session(self, session_id: str):
        """Clean up a session volume.
        
        Args:
            session_id: Session ID to clean up.
        """
        self.volume_manager.remove_session_volume(session_id)
        logger.debug(f"Cleaned up session: {session_id}")
