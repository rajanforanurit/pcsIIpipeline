from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.security import verify_access_token
from app.db.mongodb import get_db
_bearer = HTTPBearer(auto_error=True)
async def get_current_admin(credentials: HTTPAuthorizationCredentials=Depends(_bearer), db: AsyncIOMotorDatabase=Depends(get_db)) -> str:
    payload = verify_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid or expired token', headers={'WWW-Authenticate': 'Bearer'})
    username: str = payload.get('sub', '')
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Token payload missing subject')
    return username
