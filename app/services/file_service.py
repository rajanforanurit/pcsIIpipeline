import uuid
from pathlib import Path
from fastapi import UploadFile
from app.core.config import settings
from app.core.exceptions import FileSizeExceededError, InvalidFileTypeError
from app.core.logging import get_logger
logger = get_logger(__name__)
async def save_upload(file: UploadFile) -> str:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise InvalidFileTypeError(file.filename or "unknown")
    contents = await file.read()
    if len(contents) > settings.MAX_UPLOAD_SIZE:
        raise FileSizeExceededError(settings.MAX_UPLOAD_SIZE)
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    unique_name = f"{uuid.uuid4().hex}_{file.filename}"
    dest = upload_dir / unique_name
    dest.write_bytes(contents)
    logger.info("file.saved", filename=file.filename, size=len(contents), path=str(dest))
    return str(dest)
def delete_file(file_path: str) -> None:
    path = Path(file_path)
    if path.exists():
        path.unlink()
        logger.info("file.deleted", path=file_path)
