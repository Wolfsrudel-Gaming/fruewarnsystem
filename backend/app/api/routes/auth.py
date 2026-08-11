from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from app.config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

ALGORITHM = "HS256"


class Token(BaseModel):
    access_token: str
    token_type: str


class User(BaseModel):
    username: str


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Ungültige Anmeldedaten",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        return User(username=username)
    except JWTError:
        raise credentials_exception


_admin_hash = None


def _get_admin_hash():
    global _admin_hash
    if _admin_hash is None:
        _admin_hash = get_password_hash(settings.admin_password)
    return _admin_hash


@router.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if form_data.username != settings.admin_username:
        raise HTTPException(status_code=401, detail="Ungültiger Benutzername oder Passwort")

    if not verify_password(form_data.password, _get_admin_hash()):
        raise HTTPException(status_code=401, detail="Ungültiger Benutzername oder Passwort")

    access_token = create_access_token(data={"sub": form_data.username})
    return Token(access_token=access_token, token_type="bearer")


@router.get("/me")
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user
