from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.config import settings
from app.core.dependencies import get_current_admin
from app.core.logging import get_logger
from app.core.security import create_access_token, verify_password, hash_password
from app.db.mongodb import get_db
from app.models.auth import AdminInfo, LoginRequest, TokenResponse
from app.models.common import SuccessResponse
router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = get_logger(__name__)
@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest) -> TokenResponse:
    if payload.username != settings.ADMIN_ID or payload.password != settings.ADMIN_PASS:
        logger.warning("auth.login_failed", username=payload.username)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token({"sub": payload.username, "role": "admin"})
    logger.info("auth.login_success", username=payload.username)
    return TokenResponse(access_token=token, token_type="bearer", expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60)
@router.get("/me", response_model=AdminInfo)
async def get_me(current_admin: str = Depends(get_current_admin)) -> AdminInfo:
    return AdminInfo(username=current_admin, role="admin")
@router.post("/logout", response_model=SuccessResponse)
async def logout(current_admin: str = Depends(get_current_admin)) -> SuccessResponse:
    logger.info("auth.logout", username=current_admin)
    return SuccessResponse(message="Logged out successfully")
