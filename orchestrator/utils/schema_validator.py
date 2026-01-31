"""JSON schema validation for capsule inputs and outputs."""

import json
from pathlib import Path
from typing import Dict, Any, Optional
import jsonschema
import logging

logger = logging.getLogger(__name__)


class SchemaValidator:
    """Validates capsule inputs and outputs against schema.json."""
    
    def __init__(self, capsule_path: str):
        """Initialize schema validator for a capsule.
        
        Args:
            capsule_path: Path to the capsule directory containing schema.json.
        """
        self.capsule_path = Path(capsule_path)
        self.schema_path = self.capsule_path / "schema.json"
        self._schema = None
        self._load_schema()
    
    def _load_schema(self):
        """Load and parse schema.json file."""
        if not self.schema_path.exists():
            logger.warning(f"schema.json not found at {self.schema_path}")
            self._schema = None
            return
        
        try:
            with open(self.schema_path, 'r') as f:
                self._schema = json.load(f)
            logger.debug(f"Loaded schema from {self.schema_path}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in schema.json: {e}")
            self._schema = None
        except Exception as e:
            logger.error(f"Error loading schema: {e}")
            self._schema = None
    
    def validate_input(self, data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate input data against the input schema.
        
        Args:
            data: Input data dictionary to validate.
            
        Returns:
            Tuple of (is_valid, error_message). If valid, error_message is None.
        """
        if self._schema is None:
            logger.warning("No schema loaded, skipping validation")
            return True, None
        
        input_schema = self._schema.get('input')
        if input_schema is None:
            logger.debug("No input schema defined, skipping validation")
            return True, None
        
        try:
            jsonschema.validate(instance=data, schema=input_schema)
            logger.debug("Input validation passed")
            return True, None
        except jsonschema.ValidationError as e:
            error_msg = f"Input validation failed: {e.message}"
            logger.error(error_msg)
            return False, error_msg
        except jsonschema.SchemaError as e:
            error_msg = f"Schema error: {e.message}"
            logger.error(error_msg)
            return False, error_msg
    
    def validate_output(self, data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate output data against the output schema.
        
        Args:
            data: Output data dictionary to validate.
            
        Returns:
            Tuple of (is_valid, error_message). If valid, error_message is None.
        """
        if self._schema is None:
            logger.warning("No schema loaded, skipping validation")
            return True, None
        
        output_schema = self._schema.get('output')
        if output_schema is None:
            logger.debug("No output schema defined, skipping validation")
            return True, None
        
        try:
            jsonschema.validate(instance=data, schema=output_schema)
            logger.debug("Output validation passed")
            return True, None
        except jsonschema.ValidationError as e:
            error_msg = f"Output validation failed: {e.message}"
            logger.error(error_msg)
            return False, error_msg
        except jsonschema.SchemaError as e:
            error_msg = f"Schema error: {e.message}"
            logger.error(error_msg)
            return False, error_msg
    
    def get_input_schema(self) -> Optional[Dict[str, Any]]:
        """Get the input schema definition.
        
        Returns:
            Input schema dict or None if not available.
        """
        if self._schema is None:
            return None
        return self._schema.get('input')
    
    def get_output_schema(self) -> Optional[Dict[str, Any]]:
        """Get the output schema definition.
        
        Returns:
            Output schema dict or None if not available.
        """
        if self._schema is None:
            return None
        return self._schema.get('output')
