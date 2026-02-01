"""Handoff handler for inter-capsule communication."""

import uuid
from typing import Dict, Any, Optional
import logging

from .capsule_executor import CapsuleExecutor
from .file_manager import FileManager
from .exceptions import HandoffError, CapsuleNotFoundError, FileOperationError

logger = logging.getLogger(__name__)


class HandoffHandler:
    """Handles handoff requests between capsules."""
    
    def __init__(
        self,
        capsule_executor: CapsuleExecutor,
        file_manager: FileManager,
        config,
        state_tracker=None
    ):
        """Initialize handoff handler.
        
        Args:
            capsule_executor: CapsuleExecutor instance.
            file_manager: FileManager instance.
            config: Config instance.
            state_tracker: Optional StateTracker instance for monitoring.
        """
        self.capsule_executor = capsule_executor
        self.file_manager = file_manager
        self.config = config
        self.state_tracker = state_tracker
        # Track active sessions for handoff context
        self._active_sessions: Dict[str, str] = {}  # container_id -> session_id
    
    def process_handoff(
        self,
        caller_session_id: str,
        target_capsule: str,
        args: Dict[str, Any],
        orchestrator_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process a handoff request from one capsule to another.
        
        Args:
            caller_session_id: Session ID of the calling capsule.
            target_capsule: Name of the target capsule.
            args: Arguments to pass to the target capsule.
            orchestrator_url: Optional orchestrator URL for nested handoffs.
            
        Returns:
            Dictionary with 'success', 'output', 'files', and 'error' keys.
        """
        logger.info(f"Processing handoff: {caller_session_id} -> {target_capsule}")
        
        # Validate target capsule exists
        target_config = self.config.get_capsule(target_capsule)
        if not target_config:
            error_msg = f"Target capsule '{target_capsule}' not found"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
        
        # Identify file references in args
        # Files should be in caller's /io/handoff/outgoing directory
        input_files = {}
        processed_args = {}
        
        for key, value in args.items():
            if isinstance(value, str):
                # Check if this might be a file reference
                # If file exists in handoff/outgoing, treat it as a file
                if self.file_manager.file_exists_in_handoff_outgoing(caller_session_id, value):
                    input_files[value] = value  # Will be copied from outgoing
                    processed_args[key] = value  # Keep filename in args
                    logger.debug(f"Identified file reference: {key} -> {value}")
                else:
                    # Regular string value
                    processed_args[key] = value
            else:
                # Non-string value (int, float, bool, dict, list)
                processed_args[key] = value
        
        # Create a new session for the target capsule
        target_session_id = str(uuid.uuid4())
        
        # Get caller capsule name for tracking
        caller_capsule = None
        if self.state_tracker:
            caller_capsule = self.state_tracker.get_capsule_name(caller_session_id)
            # If caller not found, try to infer from container name pattern
            # Container names are like "aod-{session_id[:8]}"
            if not caller_capsule:
                logger.debug(f"Caller capsule not found for session {caller_session_id}, handoff tracking may be incomplete")
        
        try:
            # Copy files from caller's handoff/outgoing to target's input
            for filename in input_files.keys():
                try:
                    if not self.file_manager.copy_handoff_outgoing(
                        caller_session_id,
                        target_session_id,
                        filename
                    ):
                        error_msg = f"Failed to copy file to target capsule: {filename}"
                        logger.error(error_msg)
                        return {
                            "success": False,
                            "error": error_msg
                        }
                except Exception as e:
                    error_msg = f"Error copying file {filename}: {str(e)}"
                    logger.error(error_msg)
                    return {
                        "success": False,
                        "error": error_msg
                    }
            
            # Execute target capsule
            result = self.capsule_executor.execute_capsule(
                capsule_name=target_capsule,
                input_data=processed_args,
                input_files=None,  # Files already copied via handoff
                session_id=target_session_id,
                orchestrator_url=orchestrator_url,
                parent_session_id=caller_session_id
            )
            
            # Register handoff (only if we have caller capsule name)
            if self.state_tracker and caller_capsule:
                self.state_tracker.register_handoff(
                    caller_session_id=caller_session_id,
                    caller_capsule=caller_capsule,
                    target_capsule=target_capsule,
                    target_session_id=target_session_id,
                    success=result.get("success", False)
                )
            elif self.state_tracker:
                logger.warning(f"Could not register handoff: caller capsule unknown for session {caller_session_id}")
            
            if not result.get("success"):
                return result
            
            # Copy output files from target's output to caller's handoff/incoming
            output_files = result.get("files", [])
            for filename in output_files:
                try:
                    if not self.file_manager.copy_handoff_incoming(
                        target_session_id,
                        caller_session_id,
                        filename
                    ):
                        logger.warning(f"Failed to copy output file to caller: {filename}")
                except Exception as e:
                    logger.warning(f"Error copying output file {filename} to caller: {str(e)}")
            
            # Cleanup target session
            self.capsule_executor.cleanup_session(target_session_id)
            
            # Return the output data (JSON response)
            return {
                "success": True,
                "output": result.get("output", {}),
                "files": output_files
            }
            
        except Exception as e:
            logger.error(f"Error processing handoff: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
        finally:
            # Ensure target session is cleaned up even on error
            try:
                self.capsule_executor.cleanup_session(target_session_id)
            except Exception:
                pass
    
    def register_session(self, container_id: str, session_id: str):
        """Register an active session for tracking.
        
        Args:
            container_id: Docker container ID.
            session_id: Session ID.
        """
        self._active_sessions[container_id] = session_id
        logger.debug(f"Registered session: {container_id[:12]} -> {session_id}")
    
    def unregister_session(self, container_id: str):
        """Unregister a session.
        
        Args:
            container_id: Docker container ID.
        """
        if container_id in self._active_sessions:
            del self._active_sessions[container_id]
            logger.debug(f"Unregistered session: {container_id[:12]}")
    
    def get_session_id(self, container_id: str) -> Optional[str]:
        """Get session ID for a container.
        
        Args:
            container_id: Docker container ID.
            
        Returns:
            Session ID or None if not found.
        """
        return self._active_sessions.get(container_id)
