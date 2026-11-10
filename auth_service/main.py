import os, hashlib, secrets, datetime as dt
import jwt
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Mapped, mapped_column, Session
from common import Base, engine, get_db, current_user, SECRET, ALGO

STAFF_CODE = os.getenv("STAFF_CODE", "happytails-staff")   # secret needed to self-register as staff
TOKEN_HOURS = 8


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(unique=True, index=True)
    password_hash: Mapped[str]
    role: Mapped[str] = mapped_column(default="owner")   # owner | staff | admin


Base.metadata.create_all(engine)
app = FastAPI(title="Happy Tails - Auth Service")


def hash_pw(pw: str, salt: Optional[str] = None) -> str:
    salt = salt or secrets.token_hex(8)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 100_000).hex()
    return f"{salt}${h}"


def check_pw(pw: str, stored: str) -> bool:
    salt, _ = stored.split("$")
    return secrets.compare_digest(hash_pw(pw, salt), stored)


class RegisterIn(BaseModel):
    username: str
    password: str
    role: str = "owner"
    staff_code: Optional[str] = None


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    model_config = {"from_attributes": True}


@app.post("/auth/register", response_model=UserOut, status_code=201)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    if data.role not in ("owner", "staff"):
        raise HTTPException(400, "role must be 'owner' or 'staff'")
    if data.role == "staff" and data.staff_code != STAFF_CODE:
        raise HTTPException(403, "Invalid staff code")
    if db.query(User).filter_by(username=data.username).first():
        raise HTTPException(409, "Username already taken")
    user = User(username=data.username, password_hash=hash_pw(data.password), role=data.role)
    db.add(user); db.commit(); db.refresh(user)
    return user


@app.post("/auth/login")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter_by(username=form.username).first()
    if not user or not check_pw(form.password, user.password_hash):
        raise HTTPException(401, "Incorrect username or password")
    payload = {"sub": str(user.id), "username": user.username, "role": user.role,
               "exp": dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=TOKEN_HOURS)}
    return {"access_token": jwt.encode(payload, SECRET, algorithm=ALGO), "token_type": "bearer"}


@app.get("/auth/me")
def me(user: dict = Depends(current_user)):
    return user


@app.get("/health")
def health():
    return {"service": "auth", "status": "ok"}
