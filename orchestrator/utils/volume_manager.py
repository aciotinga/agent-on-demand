"""Volume and directory management for capsule sessions."""

import os
import shutil
from pathlib import Path
from typing import Optional
import logging
import uuid

logger = logging.getLogger(__name__)


class VolumeManager:
    """Manages volume directories for capsule sessions."""
    
    def __init__(self, base_path: str):
        """Initialize volume manager.
        
        Args:
            base_path: Base directory path for all volumes.
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def create_session_volume(self, session_id: Optional[str] = None) -> str:
        """Create a new session volume with required directory structure.
        
        Args:
            session_id: Optional session ID. If None, generates a unique ID.
            
        Returns:
            Path to the session volume directory.
        """
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        volume_path = self.base_path / session_id
        
        # Create directory structure
        (volume_path / "input").mkdir(parents=True, exist_ok=True)
        (volume_path / "output").mkdir(parents=True, exist_ok=True)
        (volume_path / "handoff" / "outgoing").mkdir(parents=True, exist_ok=True)
        (volume_path / "handoff" / "incoming").mkdir(parents=True, exist_ok=True)
        
        logger.debug(f"Created session volume: {volume_path}")
        return str(volume_path)
    
    def get_volume_path(self, session_id: str) -> Path:
        """Get the path to a session volume.
        
        Args:
            session_id: Session ID.
            
        Returns:
            Path to the volume directory.
        """
        return self.base_path / session_id
    
    def get_input_path(self, session_id: str) -> Path:
        """Get the input directory path for a session.
        
        Args:
            session_id: Session ID.
            
        Returns:
            Path to input directory.
        """
        return self.get_volume_path(session_id) / "input"
    
    def get_output_path(self, session_id: str) -> Path:
        """Get the output directory path for a session.
        
        Args:
            session_id: Session ID.
            
        Returns:
            Path to output directory.
        """
        return self.get_volume_path(session_id) / "output"
    
    def get_handoff_outgoing_path(self, session_id: str) -> Path:
        """Get the handoff outgoing directory path for a session.
        
        Args:
            session_id: Session ID.
            
        Returns:
            Path to handoff outgoing directory.
        """
        return self.get_volume_path(session_id) / "handoff" / "outgoing"
    
    def get_handoff_incoming_path(self, session_id: str) -> Path:
        """Get the handoff incoming directory path for a session.
        
        Args:
            session_id: Session ID.
            
        Returns:
            Path to handoff incoming directory.
        """
        return self.get_volume_path(session_id) / "handoff" / "incoming"
    
    def remove_session_volume(self, session_id: str) -> bool:
        """Remove a session volume and all its contents.
        
        Args:
            session_id: Session ID.
            
        Returns:
            True if successful, False otherwise.
        """
        volume_path = self.get_volume_path(session_id)
        
        if not volume_path.exists():
            logger.warning(f"Volume does not exist: {volume_path}")
            return False
        
        try:
            shutil.rmtree(volume_path)
            logger.debug(f"Removed session volume: {volume_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove volume {volume_path}: {e}")
            return False
    
    def volume_exists(self, session_id: str) -> bool:
        """Check if a session volume exists.
        
        Args:
            session_id: Session ID.
            
        Returns:
            True if volume exists, False otherwise.
        """
        return self.get_volume_path(session_id).exists()
    
    def cleanup_all_volumes(self) -> int:
        """Remove all session volumes.
        
        Returns:
            Number of volumes removed.
        """
        if not self.base_path.exists():
            return 0
        
        removed_count = 0
        try:
            for item in self.base_path.iterdir():
                if item.is_dir():
                    try:
                        shutil.rmtree(item)
                        removed_count += 1
                        logger.debug(f"Removed volume during cleanup: {item}")
                    except Exception as e:
                        logger.warning(f"Failed to remove volume {item} during cleanup: {e}")
            
            logger.info(f"Cleaned up {removed_count} volume(s) on shutdown")
            return removed_count
        except Exception as e:
            logger.error(f"Error during volume cleanup: {e}")
            return removed_count