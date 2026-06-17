from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.config import settings
_pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)
def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)
def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta]=None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta if expires_delta is not None else timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode['exp'] = expire
    to_encode['iat'] = datetime.now(timezone.utc)
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
def decode_access_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
def verify_access_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        return decode_access_token(token)
    except JWTError:
        return None
