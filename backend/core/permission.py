from datetime import timedelta, datetime, timezone

import jwt
from core.dependencies import oauth2_scheme, get_db, SECRET_KEY, ALGORITHM
from core.models import User
from fastapi import Depends, HTTPException, status
from jose import JWTError
from sqlalchemy.orm import Session


async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无法认证访问令牌",
                                          headers={"WWW-Authenticate": "Bearer"}, )
    expired_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="访问令牌已过期")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        expire_timestamp = payload.get("exp")
        if expire_timestamp:
            expire_time = datetime.fromtimestamp(expire_timestamp, timezone.utc)
            if expire_time - datetime.now(timezone.utc) < timedelta(minutes=0):
                raise expired_exception
        user_id = payload.get("id")
        if user_id is None:
            raise credentials_exception
    except jwt.ExpiredSignatureError:
        raise expired_exception
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return {"user": user, "id": user.id}
