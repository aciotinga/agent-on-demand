"""Custom exceptions for the orchestrator."""


class OrchestratorError(Exception):
    """Base exception for orchestrator errors."""
    pass


class CapsuleNotFoundError(OrchestratorError):
    """Raised when a capsule is not found in the registry."""
    pass


class SchemaValidationError(OrchestratorError):
    """Raised when schema validation fails."""
    pass


class DockerOperationError(OrchestratorError):
    """Raised when a Docker operation fails."""
    pass


class FileOperationError(OrchestratorError):
    """Raised when a file operation fails."""
    pass


class HandoffError(OrchestratorError):
    """Raised when a handoff operation fails."""
    pass
