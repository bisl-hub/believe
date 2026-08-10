from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from fastapi.security import OAuth2PasswordBearer

from ..db.session import get_db
from ..models import user as user_model
from ..schemas import user as user_schema
from ..core import config, security

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/token")

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(user_model.User).filter(user_model.User.email == email).first()
    if user is None:
        raise credentials_exception
    return user

@router.get("/me", response_model=user_schema.UserResponse)
def read_users_me(current_user: user_model.User = Depends(get_current_user)):
    return current_user

@router.put("/me/email", response_model=user_schema.UserResponse)
def update_email(
    body: user_schema.UserUpdateEmail,
    current_user: user_model.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not security.verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    existing = db.query(user_model.User).filter(
        user_model.User.email == body.email,
        user_model.User.id != current_user.id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already in use")
    current_user.email = body.email
    db.commit()
    db.refresh(current_user)
    return current_user

@router.put("/me/password", status_code=204)
def update_password(
    body: user_schema.UserUpdatePassword,
    current_user: user_model.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not security.verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    current_user.hashed_password = security.get_password_hash(body.new_password)
    db.commit()
