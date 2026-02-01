"""State tracker for monitoring running capsules and handoffs."""

import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
import threading
import logging

logger = logging.getLogger(__name__)


@dataclass
class CapsuleExecution:
    """Represents a capsule execution instance."""
    session_id: str
    capsule_name: str
    start_time: float
    status: str  # 'running', 'completed', 'failed'
    container_id: Optional[str] = None
    parent_session_id: Optional[str] = None  # If this was spawned from a handoff


@dataclass
class Handoff:
    """Represents a handoff from one capsule to another."""
    caller_session_id: str
    caller_capsule: str
    target_capsule: str
    target_session_id: str
    timestamp: float
    success: bool = True


class StateTracker:
    """Tracks running capsules and handoffs for visualization."""
    
    def __init__(self):
        """Initialize state tracker."""
        self._lock = threading.Lock()
        # session_id -> CapsuleExecution
        self._executions: Dict[str, CapsuleExecution] = {}
        # List of all handoffs (for history)
        self._handoffs: List[Handoff] = []
        # Keep last N handoffs to avoid memory bloat
        self._max_handoff_history = 1000
    
    def register_execution(
        self,
        session_id: str,
        capsule_name: str,
        container_id: Optional[str] = None,
        parent_session_id: Optional[str] = None
    ):
        """Register a new capsule execution.
        
        Args:
            session_id: Unique session ID.
            capsule_name: Name of the capsule being executed.
            container_id: Optional container ID.
            parent_session_id: Optional parent session if spawned from handoff.
        """
        with self._lock:
            execution = CapsuleExecution(
                session_id=session_id,
                capsule_name=capsule_name,
                start_time=time.time(),
                status='running',
                container_id=container_id,
                parent_session_id=parent_session_id
            )
            self._executions[session_id] = execution
            logger.debug(f"Registered execution: {session_id} -> {capsule_name}")
    
    def update_execution_status(
        self,
        session_id: str,
        status: str,
        container_id: Optional[str] = None
    ):
        """Update the status of an execution.
        
        Args:
            session_id: Session ID.
            status: New status ('running', 'completed', 'failed').
            container_id: Optional container ID to update.
        """
        with self._lock:
            if session_id in self._executions:
                self._executions[session_id].status = status
                if container_id:
                    self._executions[session_id].container_id = container_id
                logger.debug(f"Updated execution status: {session_id} -> {status}")
    
    def unregister_execution(self, session_id: str):
        """Unregister a completed execution.
        
        Args:
            session_id: Session ID to unregister.
        """
        with self._lock:
            if session_id in self._executions:
                # Mark as completed before removing
                self._executions[session_id].status = 'completed'
                # Keep for a bit for visualization, but mark as completed
                logger.debug(f"Unregistered execution: {session_id}")
    
    def register_handoff(
        self,
        caller_session_id: str,
        caller_capsule: str,
        target_capsule: str,
        target_session_id: str,
        success: bool = True
    ):
        """Register a handoff between capsules.
        
        Args:
            caller_session_id: Session ID of the calling capsule.
            caller_capsule: Name of the calling capsule.
            target_capsule: Name of the target capsule.
            target_session_id: Session ID of the target capsule.
            success: Whether the handoff was successful.
        """
        with self._lock:
            handoff = Handoff(
                caller_session_id=caller_session_id,
                caller_capsule=caller_capsule,
                target_capsule=target_capsule,
                target_session_id=target_session_id,
                timestamp=time.time(),
                success=success
            )
            self._handoffs.append(handoff)
            
            # Trim history if too long
            if len(self._handoffs) > self._max_handoff_history:
                self._handoffs = self._handoffs[-self._max_handoff_history:]
            
            logger.debug(f"Registered handoff: {caller_capsule} -> {target_capsule}")
    
    def get_state(self) -> Dict[str, Any]:
        """Get current state for visualization.
        
        Returns:
            Dictionary with nodes (executions/sessions) and edges (handoffs).
        """
        with self._lock:
            # Get all active and recent executions
            now = time.time()
            active_executions = []
            
            for session_id, execution in self._executions.items():
                # Include running or recently completed (within last 30 seconds)
                age = now - execution.start_time
                if execution.status == 'running' or (execution.status in ('completed', 'failed') and age < 30):
                    active_executions.append(execution)
            
            # Build nodes - one node per execution (session)
            nodes = []
            active_session_ids = {e.session_id for e in active_executions}
            
            for execution in active_executions:
                nodes.append({
                    'id': execution.session_id,
                    'session_id': execution.session_id,
                    'capsule_name': execution.capsule_name,
                    'status': execution.status,
                    'start_time': execution.start_time,
                    'container_id': execution.container_id,
                    'parent_session_id': execution.parent_session_id
                })
            
            # Build edges (handoffs) - connect from caller_session_id to target_session_id
            edges = []
            
            for handoff in self._handoffs:
                # Include handoff if either caller or target is in active sessions
                # or if it's recent (within last 60 seconds)
                age = now - handoff.timestamp
                if (handoff.caller_session_id in active_session_ids or 
                    handoff.target_session_id in active_session_ids or
                    age < 60):
                    edges.append({
                        'from': handoff.caller_session_id,
                        'to': handoff.target_session_id,
                        'caller_capsule': handoff.caller_capsule,
                        'target_capsule': handoff.target_capsule,
                        'timestamp': handoff.timestamp,
                        'success': handoff.success
                    })
            
            return {
                'nodes': nodes,
                'edges': edges,
                'timestamp': now
            }
    
    def get_capsule_name(self, session_id: str) -> Optional[str]:
        """Get capsule name for a session ID.
        
        Args:
            session_id: Session ID.
            
        Returns:
            Capsule name or None if not found.
        """
        with self._lock:
            execution = self._executions.get(session_id)
            return execution.capsule_name if execution else None
