"""Main HTTP server for the orchestrator."""

import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Handle imports when run directly or as a module
# Add parent directory to path when running directly
parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

from orchestrator.config_loader import Config
from orchestrator.docker_client import DockerClient
from orchestrator.file_manager import FileManager
from orchestrator.utils.volume_manager import VolumeManager
from orchestrator.capsule_executor import CapsuleExecutor
from orchestrator.handoff_handler import HandoffHandler
from orchestrator.state_tracker import StateTracker
from orchestrator.exceptions import OrchestratorError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    global config, docker_client, volume_manager, file_manager
    global capsule_executor, handoff_handler, state_tracker, executor
    
    try:
        logger.info("Initializing orchestrator...")
        
        # Load configuration
        config = Config()
        logger.info(f"Loaded configuration from {config.config_path}")
        
        # Initialize Docker client
        docker_config = config.docker_config
        network_name = docker_config.get('network', 'aod-network')
        docker_client = DockerClient(network_name=network_name)
        logger.info(f"Docker client initialized with network: {network_name}")
        
        # Initialize volume manager
        base_path = docker_config.get('base_path', './volumes')
        volume_manager = VolumeManager(base_path)
        logger.info(f"Volume manager initialized with base path: {base_path}")
        
        # Initialize file manager
        file_manager = FileManager(volume_manager)
        logger.info("File manager initialized")
        
        # Initialize capsule executor
        capsule_executor = CapsuleExecutor(
            docker_client=docker_client,
            file_manager=file_manager,
            volume_manager=volume_manager,
            config=config
        )
        logger.info("Capsule executor initialized")
        
        # Initialize state tracker
        state_tracker = StateTracker()
        logger.info("State tracker initialized")
        
        # Initialize handoff handler
        handoff_handler = HandoffHandler(
            capsule_executor=capsule_executor,
            file_manager=file_manager,
            config=config,
            state_tracker=state_tracker
        )
        logger.info("Handoff handler initialized")
        
        # Set state tracker in capsule executor
        capsule_executor.set_state_tracker(state_tracker)
        
        # Create thread pool executor for running blocking capsule execution
        executor = ThreadPoolExecutor(max_workers=10)
        logger.info("Thread pool executor initialized for concurrent capsule execution")
        
        # Rebuild all capsule containers on startup
        logger.info("Rebuilding all capsule containers on startup...")
        for capsule_name, capsule_config in config.capsules.items():
            image_name = capsule_config['image']
            capsule_path = capsule_config['path']
            logger.info(f"Rebuilding container for capsule: {capsule_name} (image: {image_name})")
            success = docker_client.build_capsule(image_name, capsule_path)
            if success:
                logger.info(f"Successfully rebuilt container for capsule: {capsule_name}")
            else:
                logger.warning(f"Failed to rebuild container for capsule: {capsule_name}")
        
        logger.info("Orchestrator initialization complete")
        
    except Exception as e:
        logger.error(f"Failed to initialize orchestrator: {e}", exc_info=True)
        # Re-raise the exception so FastAPI can handle it properly
        raise
    
    yield
    
    # Shutdown - clean up all volumes and thread pool
    logger.info("Shutting down orchestrator...")
    try:
        if executor:
            executor.shutdown(wait=True)
            logger.info("Thread pool executor shut down")
        if volume_manager:
            removed_count = volume_manager.cleanup_all_volumes()
            logger.info(f"Cleaned up {removed_count} volume(s) on shutdown")
    except Exception as e:
        logger.error(f"Error during shutdown cleanup: {e}", exc_info=True)


# Initialize FastAPI app
app = FastAPI(
    title="AOD Orchestrator",
    description="Central management unit for Agent-On-Demand capsules",
    version="0.1.0",
    lifespan=lifespan
)

# Global components (initialized in startup)
config: Optional[Config] = None
docker_client: Optional[DockerClient] = None
volume_manager: Optional[VolumeManager] = None
file_manager: Optional[FileManager] = None
capsule_executor: Optional[CapsuleExecutor] = None
handoff_handler: Optional[HandoffHandler] = None
state_tracker: Optional[StateTracker] = None
executor: Optional[ThreadPoolExecutor] = None


# Request/Response models
class ExecuteRequest(BaseModel):
    """Request model for capsule execution."""
    capsule: str
    input: Dict[str, Any]
    files: Optional[Dict[str, str]] = None


class HandoffRequest(BaseModel):
    """Request model for handoff operations."""
    session_id: str
    target: str
    args: Dict[str, Any]


class ExecuteResponse(BaseModel):
    """Response model for capsule execution."""
    success: bool
    output: Optional[Dict[str, Any]] = None
    files: Optional[list] = None
    error: Optional[str] = None
    session_id: Optional[str] = None


class HandoffResponse(BaseModel):
    """Response model for handoff operations."""
    success: bool
    output: Optional[Dict[str, Any]] = None
    files: Optional[list] = None
    error: Optional[str] = None




@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "AOD Orchestrator"
    }


@app.post("/execute", response_model=ExecuteResponse)
async def execute_capsule(request: ExecuteRequest):
    """Execute a capsule.
    
    Args:
        request: ExecuteRequest with capsule name, input data, and optional files.
        
    Returns:
        ExecuteResponse with execution results.
    """
    if not capsule_executor:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    
    if not request.capsule:
        raise HTTPException(status_code=400, detail="Capsule name is required")
    
    try:
        logger.info(f"Executing capsule: {request.capsule}")
        
        orchestrator_url = config.get_orchestrator_url()
        
        # Run blocking execute_capsule in thread pool to allow concurrent requests
        # This is critical for workflow capsules that make HTTP requests back to orchestrator
        if not executor:
            raise HTTPException(status_code=503, detail="Thread pool executor not initialized")
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            executor,
            capsule_executor.execute_capsule,
            request.capsule,
            request.input,
            request.files,
            None,  # session_id
            orchestrator_url,
            None   # parent_session_id
        )
        
        if result.get("success"):
            logger.info(f"Capsule execution successful: {request.capsule}")
        else:
            logger.error(f"Capsule execution failed: {result.get('error')}")
        
        return ExecuteResponse(**result)
        
    except OrchestratorError as e:
        logger.error(f"Orchestrator error executing capsule: {e}")
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error executing capsule: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.post("/handoff", response_model=HandoffResponse)
async def handle_handoff(request: HandoffRequest):
    """Handle inter-capsule handoff request.
    
    Args:
        request: HandoffRequest with caller session ID, target capsule, and args.
        
    Returns:
        HandoffResponse with handoff results.
    """
    if not handoff_handler:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    
    if not request.session_id:
        raise HTTPException(status_code=400, detail="Session ID is required")
    
    if not request.target:
        raise HTTPException(status_code=400, detail="Target capsule is required")
    
    try:
        logger.info(f"Handoff request: {request.session_id} -> {request.target}")
        
        orchestrator_url = config.get_orchestrator_url()
        
        result = handoff_handler.process_handoff(
            caller_session_id=request.session_id,
            target_capsule=request.target,
            args=request.args,
            orchestrator_url=orchestrator_url
        )
        
        if result.get("success"):
            logger.info(f"Handoff successful: {request.session_id} -> {request.target}")
        else:
            logger.error(f"Handoff failed: {result.get('error')}")
        
        return HandoffResponse(**result)
        
    except OrchestratorError as e:
        logger.error(f"Orchestrator error processing handoff: {e}")
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error processing handoff: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.get("/capsules")
async def list_capsules():
    """List all available capsules.
    
    Returns:
        Dictionary mapping capsule names to their configurations.
    """
    if not config:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    
    capsules = {}
    for name, capsule_config in config.capsules.items():
        capsules[name] = {
            "path": capsule_config["path"],
            "image": capsule_config["image"]
        }
    
    return {"capsules": capsules}


@app.get("/capsules/{capsule_name}/schema")
async def get_capsule_schema(capsule_name: str):
    """Get the schema for a specific capsule.
    
    Args:
        capsule_name: Name of the capsule.
        
    Returns:
        Dictionary containing the capsule's schema.json content.
    """
    if not config:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    
    capsule_config = config.get_capsule(capsule_name)
    if not capsule_config:
        raise HTTPException(status_code=404, detail=f"Capsule '{capsule_name}' not found")
    
    capsule_path = Path(capsule_config['path'])
    schema_path = capsule_path / "schema.json"
    
    if not schema_path.exists():
        raise HTTPException(status_code=404, detail=f"Schema not found for capsule '{capsule_name}'")
    
    try:
        import json
        with open(schema_path, 'r') as f:
            schema = json.load(f)
        return schema
    except Exception as e:
        logger.error(f"Error reading schema for {capsule_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Error reading schema: {str(e)}")


@app.get("/visualizer/state")
async def get_visualizer_state():
    """Get current state for the visualizer.
    
    Returns:
        Dictionary with nodes (capsules) and edges (handoffs).
    """
    if not state_tracker:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    
    return state_tracker.get_state()


@app.get("/visualizer")
async def get_visualizer():
    """Serve the visualizer HTML page.
    
    Returns:
        HTML file for the visualizer.
    """
    visualizer_path = Path(__file__).parent / "visualizer.html"
    if not visualizer_path.exists():
        raise HTTPException(status_code=404, detail="Visualizer not found")
    return FileResponse(visualizer_path)


def main():
    """Main entry point for the orchestrator server."""
    import uvicorn
    
    # Load config early to get server settings
    try:
        temp_config = Config()
        server_config = temp_config.server_config
        host = server_config.get('host', '0.0.0.0')
        port = server_config.get('port', 8000)
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}", exc_info=True)
        sys.exit(1)
    
    logger.info(f"Starting orchestrator server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
