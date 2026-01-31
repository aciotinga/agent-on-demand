"""File I/O operations for capsule volumes."""

import json
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)


class FileManager:
    """Manages file operations for capsule volumes."""
    
    def __init__(self, volume_manager):
        """Initialize file manager.
        
        Args:
            volume_manager: VolumeManager instance for path resolution.
        """
        self.volume_manager = volume_manager
    
    def copy_to_input(self, source_path: str, session_id: str, filename: Optional[str] = None) -> bool:
        """Copy a file to the input directory of a session volume.
        
        Args:
            source_path: Path to the source file.
            session_id: Target session ID.
            filename: Optional target filename. If None, uses source filename.
            
        Returns:
            True if successful, False otherwise.
        """
        source = Path(source_path)
        if not source.exists():
            logger.error(f"Source file does not exist: {source_path}")
            return False
        
        target_dir = self.volume_manager.get_input_path(session_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        
        if filename is None:
            filename = source.name
        
        target = target_dir / filename
        
        try:
            shutil.copy2(source, target)
            logger.debug(f"Copied {source_path} to {target}")
            return True
        except Exception as e:
            logger.error(f"Failed to copy file to input: {e}")
            return False
    
    def copy_from_output(self, session_id: str, filename: str, target_path: str) -> bool:
        """Copy a file from the output directory of a session volume.
        
        Args:
            session_id: Source session ID.
            filename: Name of the file in the output directory.
            target_path: Destination path for the file.
            
        Returns:
            True if successful, False otherwise.
        """
        source = self.volume_manager.get_output_path(session_id) / filename
        if not source.exists():
            logger.error(f"Output file does not exist: {source}")
            return False
        
        target = Path(target_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            shutil.copy2(source, target)
            logger.debug(f"Copied {source} to {target_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to copy file from output: {e}")
            return False
    
    def copy_handoff_outgoing(self, source_session_id: str, target_session_id: str, filename: str) -> bool:
        """Copy a file from source session's handoff/outgoing to target session's input.
        
        Args:
            source_session_id: Source session ID.
            target_session_id: Target session ID.
            filename: Name of the file to copy.
            
        Returns:
            True if successful, False otherwise.
        """
        source = self.volume_manager.get_handoff_outgoing_path(source_session_id) / filename
        if not source.exists():
            logger.error(f"Handoff outgoing file does not exist: {source}")
            return False
        
        target_dir = self.volume_manager.get_input_path(target_session_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / filename
        
        try:
            shutil.copy2(source, target)
            logger.debug(f"Copied handoff file {source} to {target}")
            return True
        except Exception as e:
            logger.error(f"Failed to copy handoff outgoing file: {e}")
            return False
    
    def copy_handoff_incoming(self, source_session_id: str, target_session_id: str, filename: str) -> bool:
        """Copy a file from source session's output to target session's handoff/incoming.
        
        Args:
            source_session_id: Source session ID (the capsule that generated the file).
            target_session_id: Target session ID (the capsule waiting for the result).
            filename: Name of the file to copy.
            
        Returns:
            True if successful, False otherwise.
        """
        source = self.volume_manager.get_output_path(source_session_id) / filename
        if not source.exists():
            logger.error(f"Source output file does not exist: {source}")
            return False
        
        target_dir = self.volume_manager.get_handoff_incoming_path(target_session_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / filename
        
        try:
            shutil.copy2(source, target)
            logger.debug(f"Copied handoff file {source} to {target}")
            return True
        except Exception as e:
            logger.error(f"Failed to copy handoff incoming file: {e}")
            return False
    
    def write_input_json(self, session_id: str, payload: Dict[str, Any]) -> bool:
        """Write input JSON payload to the session volume.
        
        Args:
            session_id: Session ID.
            payload: Input data dictionary.
            
        Returns:
            True if successful, False otherwise.
        """
        volume_path = self.volume_manager.get_volume_path(session_id)
        json_path = volume_path / "input.json"
        
        try:
            with open(json_path, 'w') as f:
                json.dump(payload, f, indent=2)
            logger.debug(f"Wrote input JSON to {json_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to write input JSON: {e}")
            return False
    
    def read_output_json(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Read output JSON from the session volume.
        
        Args:
            session_id: Session ID.
            
        Returns:
            Output data dictionary or None if not found/error.
        """
        volume_path = self.volume_manager.get_volume_path(session_id)
        json_path = volume_path / "output.json"
        
        if not json_path.exists():
            logger.warning(f"Output JSON not found: {json_path}")
            return None
        
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)
            logger.debug(f"Read output JSON from {json_path}")
            return data
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in output.json: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to read output JSON: {e}")
            return None
    
    def list_output_files(self, session_id: str) -> List[str]:
        """List all files in the output directory.
        
        Args:
            session_id: Session ID.
            
        Returns:
            List of filenames in the output directory.
        """
        output_path = self.volume_manager.get_output_path(session_id)
        if not output_path.exists():
            return []
        
        try:
            files = [f.name for f in output_path.iterdir() if f.is_file()]
            return files
        except Exception as e:
            logger.error(f"Failed to list output files: {e}")
            return []
    
    def file_exists_in_handoff_outgoing(self, session_id: str, filename: str) -> bool:
        """Check if a file exists in the handoff/outgoing directory.
        
        Args:
            session_id: Session ID.
            filename: Filename to check.
            
        Returns:
            True if file exists, False otherwise.
        """
        file_path = self.volume_manager.get_handoff_outgoing_path(session_id) / filename
        return file_path.exists()
