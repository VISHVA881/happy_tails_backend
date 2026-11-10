"""Shared helpers copied into every service: DB setup + JWT verification."""
import os
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

SECRET = os.getenv("JWT_SECRET", "change-this-secret")
ALGO = "HS256"

engine = create_engine(os.getenv("DB_URL", "sqlite:///./app.db"),
                       connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


oauth2 = OAuth2PasswordBearer(tokenUrl=os.getenv("TOKEN_URL", "http://localhost:8001/auth/login"))


def current_user(token: str = Depends(oauth2)) -> dict:
    try:
        p = jwt.decode(token, SECRET, algorithms=[ALGO])
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired token")
    return {"id": int(p["sub"]), "username": p["username"], "role": p["role"]}


def staff_only(user: dict = Depends(current_user)) -> dict:
    if user["role"] not in ("staff", "admin"):
        raise HTTPException(403, "Staff access only")
    return user
