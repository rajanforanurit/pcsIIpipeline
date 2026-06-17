from functools import lru_cache
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Auth
    ADMIN_ID: str
    ADMIN_PASS: str
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # MongoDB
    MONGODB_URI: str
    MONGODB_DB_NAME: str = "pcs_question_db"

    # AI (DeepSeek V3.2 via Azure)
    PCS2: str
    PCS2_API: str
    AI_MODEL_DEPLOYMENT: str

    # Google Drive
    GOOGLE_SERVICE_ACCOUNT_JSON: str = ""
    GOOGLE_DRIVE_ROOT_FOLDER_ID: str = ""
    GOOGLE_DRIVE_UNPROCESSED_FOLDER_ID: str = ""
    GOOGLE_DRIVE_PENDING_JSON_FOLDER_ID: str = ""
    GOOGLE_DRIVE_PROCESSED_JSON_FOLDER_ID: str = ""
    GOOGLE_DRIVE_PROCESSED_PDF_FOLDER_ID: str = ""
    GOOGLE_DRIVE_PROCESSED_LOG_FOLDER_ID: str = ""
    GOOGLE_DRIVE_FAILED_FOLDER_ID: str = ""

    # Pipeline tuning
    CHECK_INTERVAL_SECONDS: int = 60
    MAX_CONCURRENT_WORKERS: int = 2
    TEMP_DIR: str = "/tmp/pcs_pipeline"
    LOG_LEVEL: str = "INFO"
    PIPELINE_MODE: str = "auto"          # "auto" | "manual"
    ENABLE_DUPLICATE_CHECK: bool = True
    DELETE_LOCAL_TEMP_FILES: bool = True

    # Misc
    MAX_UPLOAD_SIZE: int = 73400320
    LOG_DIR: str = "/tmp/logs"
    OCR_LANGUAGE: str = "en"
    PADDLE_USE_GPU: bool = False

    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:8080"

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def ai_configured(self) -> bool:
        return bool(self.PCS2 and self.PCS2_API)

    @property
    def google_drive_configured(self) -> bool:
        return bool(
            self.GOOGLE_SERVICE_ACCOUNT_JSON
            and self.GOOGLE_DRIVE_UNPROCESSED_FOLDER_ID
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
