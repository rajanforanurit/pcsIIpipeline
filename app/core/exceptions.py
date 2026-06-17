from typing import Any, Dict, Optional


class PlatformException(Exception):
    def __init__(self, message: str, status_code: int = 500, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class AuthenticationError(PlatformException):
    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(message, status_code=401)


class AuthorizationError(PlatformException):
    def __init__(self, message: str = "Insufficient permissions") -> None:
        super().__init__(message, status_code=403)


class NotFoundError(PlatformException):
    def __init__(self, resource: str, identifier: str) -> None:
        super().__init__(f"{resource} not found: {identifier}", status_code=404,
                         details={"resource": resource, "id": identifier})


class DuplicateResourceError(PlatformException):
    def __init__(self, resource: str, identifier: str) -> None:
        super().__init__(f"{resource} already exists: {identifier}", status_code=409,
                         details={"resource": resource, "id": identifier})


class ValidationError(PlatformException):
    def __init__(self, message: str, errors: Optional[list] = None) -> None:
        super().__init__(message, status_code=422, details={"errors": errors or []})


class FileSizeExceededError(PlatformException):
    def __init__(self, max_bytes: int) -> None:
        super().__init__(f"File exceeds maximum allowed size of {max_bytes // (1024 * 1024)} MB",
                         status_code=413, details={"max_bytes": max_bytes})


class InvalidFileTypeError(PlatformException):
    def __init__(self, filename: str) -> None:
        super().__init__(f"File '{filename}' is not a supported type. Only PDF files are accepted.",
                         status_code=415, details={"filename": filename})


class PDFProcessingError(PlatformException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, status_code=500, details=details or {})


class JobNotFoundError(NotFoundError):
    def __init__(self, job_id: str) -> None:
        super().__init__("IngestionJob", job_id)


class JobStateError(PlatformException):
    def __init__(self, job_id: str, current_state: str, required_state: str) -> None:
        super().__init__(f"Job {job_id} is in state '{current_state}', expected '{required_state}'",
                         status_code=409,
                         details={"job_id": job_id, "current_state": current_state, "required_state": required_state})


class AIProviderError(PlatformException):
    def __init__(self, message: str, provider: str = "unknown") -> None:
        super().__init__(f"AI provider error ({provider}): {message}", status_code=502,
                         details={"provider": provider})


class AIProviderNotConfiguredError(PlatformException):
    def __init__(self) -> None:
        super().__init__("AI provider is not configured. Set PCS2 and PCS2_API environment variables.",
                         status_code=503)


class GoogleDriveError(PlatformException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(f"Google Drive error: {message}", status_code=502, details=details or {})


class GoogleDriveNotConfiguredError(PlatformException):
    def __init__(self) -> None:
        super().__init__("Google Drive is not configured. Set GOOGLE_SERVICE_ACCOUNT_JSON and folder IDs.",
                         status_code=503)


class PipelineError(PlatformException):
    def __init__(self, message: str, stage: str = "unknown", details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(f"Pipeline error at [{stage}]: {message}", status_code=500,
                         details={"stage": stage, **(details or {})})
