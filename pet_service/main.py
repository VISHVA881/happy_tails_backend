from typing import Optional
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Mapped, mapped_column, Session
from common import Base, engine, get_db, current_user


class Pet(Base):
    __tablename__ = "pets"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(index=True)    # user id from auth service
    name: Mapped[str]
    species: Mapped[str]                                  # dog, cat, rabbit...
    breed: Mapped[str] = mapped_column(default="")
    age: Mapped[int] = mapped_column(default=0)
    notes: Mapped[str] = mapped_column(default="")        # allergies, temperament...


Base.metadata.create_all(engine)
app = FastAPI(title="Happy Tails - Pet Profiles Service")


class PetIn(BaseModel):
    name: str
    species: str
    breed: str = ""
    age: int = 0
    notes: str = ""


class PetOut(PetIn):
    id: int
    owner_id: int
    model_config = {"from_attributes": True}


def _get_allowed(pet_id: int, user: dict, db: Session) -> Pet:
    pet = db.get(Pet, pet_id)
    if not pet:
        raise HTTPException(404, "Pet not found")
    if user["role"] == "owner" and pet.owner_id != user["id"]:
        raise HTTPException(403, "Not your pet")
    return pet


@app.post("/pets", response_model=PetOut, status_code=201)
def add_pet(data: PetIn, owner_id: Optional[int] = None, user=Depends(current_user), db: Session = Depends(get_db)):
    # owners always add to themselves; staff may add on behalf of an owner
    oid = owner_id if (user["role"] != "owner" and owner_id) else user["id"]
    pet = Pet(owner_id=oid, **data.model_dump())
    db.add(pet); db.commit(); db.refresh(pet)
    return pet


@app.get("/pets", response_model=list[PetOut])
def list_pets(owner_id: Optional[int] = None, user=Depends(current_user), db: Session = Depends(get_db)):
    q = db.query(Pet)
    if user["role"] == "owner":
        q = q.filter(Pet.owner_id == user["id"])
    elif owner_id:
        q = q.filter(Pet.owner_id == owner_id)
    return q.order_by(Pet.name).all()


@app.get("/pets/{pet_id}", response_model=PetOut)
def get_pet(pet_id: int, user=Depends(current_user), db: Session = Depends(get_db)):
    return _get_allowed(pet_id, user, db)


@app.put("/pets/{pet_id}", response_model=PetOut)
def update_pet(pet_id: int, data: PetIn, user=Depends(current_user), db: Session = Depends(get_db)):
    pet = _get_allowed(pet_id, user, db)
    for k, v in data.model_dump().items():
        setattr(pet, k, v)
    db.commit(); db.refresh(pet)
    return pet


@app.delete("/pets/{pet_id}", status_code=204)
def delete_pet(pet_id: int, user=Depends(current_user), db: Session = Depends(get_db)):
    pet = _get_allowed(pet_id, user, db)
    db.delete(pet); db.commit()


@app.get("/health")
def health():
    return {"service": "pets", "status": "ok"}
