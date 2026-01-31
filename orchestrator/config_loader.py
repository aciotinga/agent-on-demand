"""Configuration loader for the orchestrator."""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class Config:
    """Configuration manager for the orchestrator."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize configuration from YAML file.
        
        Args:
            config_path: Path to config.yaml file. If None, looks for config.yaml
                        in the orchestrator directory.
        """
        if config_path is None:
            # Default to config.yaml in orchestrator directory
            config_path = Path(__file__).parent / "config.yaml"
        
        self.config_path = Path(config_path)
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(self.config_path, 'r') as f:
            self._config = yaml.safe_load(f)
        
        # Validate and normalize paths
        self._normalize_paths()
        self._validate_capsules()
    
    def _normalize_paths(self):
        """Normalize all paths in configuration to absolute paths."""
        # Normalize capsule paths
        config_dir = self.config_path.parent
        for capsule_name, capsule_config in self._config.get('capsules', {}).items():
            if 'path' in capsule_config:
                path = Path(capsule_config['path'])
                if not path.is_absolute():
                    path = (config_dir / path).resolve()
                capsule_config['path'] = str(path)
        
        # Normalize volume base path
        if 'docker' in self._config and 'base_path' in self._config['docker']:
            base_path = Path(self._config['docker']['base_path'])
            if not base_path.is_absolute():
                base_path = (config_dir / base_path).resolve()
            self._config['docker']['base_path'] = str(base_path)
    
    def _validate_capsules(self):
        """Validate that all registered capsules exist."""
        for capsule_name, capsule_config in self._config.get('capsules', {}).items():
            capsule_path = Path(capsule_config['path'])
            if not capsule_path.exists():
                logger.warning(f"Capsule '{capsule_name}' path does not exist: {capsule_path}")
            elif not (capsule_path / "Dockerfile").exists():
                logger.warning(f"Capsule '{capsule_name}' missing Dockerfile: {capsule_path}")
            elif not (capsule_path / "schema.json").exists():
                logger.warning(f"Capsule '{capsule_name}' missing schema.json: {capsule_path}")
    
    @property
    def capsules(self) -> Dict[str, Dict[str, Any]]:
        """Get capsule registry."""
        return self._config.get('capsules', {})
    
    def get_capsule(self, capsule_name: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific capsule.
        
        Args:
            capsule_name: Name of the capsule.
            
        Returns:
            Capsule configuration dict or None if not found.
        """
        return self.capsules.get(capsule_name)
    
    @property
    def docker_config(self) -> Dict[str, Any]:
        """Get Docker configuration."""
        return self._config.get('docker', {})
    
    @property
    def server_config(self) -> Dict[str, Any]:
        """Get server configuration."""
        return self._config.get('server', {})
    
    def get_orchestrator_url(self) -> str:
        """Get the orchestrator URL for handoff requests.
        
        Returns:
            URL string in format http://host:port
        """
        host = self.server_config.get('host', '0.0.0.0')
        port = self.server_config.get('port', 8000)
        # For containers, use host.docker.internal or the actual host
        if host == '0.0.0.0':
            # When running in Docker, containers need to reach host
            return f"http://host.docker.internal:{port}"
        return f"http://{host}:{port}"
    
    @property
    def llm_config(self) -> Dict[str, Any]:
        """Get LLM configuration."""
        return self._config.get('llm', {})
    
    def get_llm_api_base(self) -> str:
        """Get the LLM API base URL for capsules.
        
        Returns:
            API base URL string (e.g., http://192.168.0.186:4000)
        """
        return self.llm_config.get('api_base', 'http://192.168.0.186:4000')
    
    def get_llm_api_key(self) -> str:
        """Get the LLM API key for capsules.
        
        Returns:
            API key string. Checks environment variable OPENAI_API_KEY first,
            then config file, then defaults to 'dummy'.
        """
        # Check environment variable first (for security)
        env_key = os.environ.get('OPENAI_API_KEY')
        if env_key:
            return env_key
        
        # Then check config file
        config_key = self.llm_config.get('api_key', 'dummy')
        # Handle both None and empty string - default to 'dummy' for LiteLLM proxy
        if config_key is None or config_key == "":
            return 'dummy'
        return config_key
