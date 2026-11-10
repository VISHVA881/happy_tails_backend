from typing import Optional
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Mapped, mapped_column, Session
from common import Base, engine, get_db, current_user, staff_only


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(unique=True, index=True)   # id from auth service
    full_name: Mapped[str]
    phone: Mapped[str] = mapped_column(default="")
    email: Mapped[str] = mapped_column(default="")
    address: Mapped[str] = mapped_column(default="")
    notes: Mapped[str] = mapped_column(default="")                  # staff notes, preferences...


Base.metadata.create_all(engine)
app = FastAPI(title="Happy Tails - Customer Records Service")


class CustomerIn(BaseModel):
    full_name: str
    phone: str = ""
    email: str = ""
    address: str = ""
    notes: str = ""


class CustomerOut(CustomerIn):
    id: int
    user_id: int
    model_config = {"from_attributes": True}


def _upsert(user_id: int, data: CustomerIn, db: Session) -> Customer:
    c = db.query(Customer).filter_by(user_id=user_id).first()
    if c:
        for k, v in data.model_dump().items():
            setattr(c, k, v)
    else:
        c = Customer(user_id=user_id, **data.model_dump())
        db.add(c)
    db.commit(); db.refresh(c)
    return c


@app.put("/customers/me", response_model=CustomerOut)
def save_my_record(data: CustomerIn, user=Depends(current_user), db: Session = Depends(get_db)):
    return _upsert(user["id"], data, db)


@app.get("/customers/me", response_model=CustomerOut)
def my_record(user=Depends(current_user), db: Session = Depends(get_db)):
    c = db.query(Customer).filter_by(user_id=user["id"]).first()
    if not c:
        raise HTTPException(404, "No customer record yet")
    return c


@app.get("/customers", response_model=list[CustomerOut])
def list_customers(q: Optional[str] = None, _=Depends(staff_only), db: Session = Depends(get_db)):
    query = db.query(Customer)
    if q:
        query = query.filter(Customer.full_name.ilike(f"%{q}%"))
    return query.order_by(Customer.full_name).all()


@app.get("/customers/{user_id}", response_model=CustomerOut)
def get_customer(user_id: int, _=Depends(staff_only), db: Session = Depends(get_db)):
    c = db.query(Customer).filter_by(user_id=user_id).first()
    if not c:
        raise HTTPException(404, "Customer not found")
    return c


@app.put("/customers/{user_id}", response_model=CustomerOut)
def staff_update_customer(user_id: int, data: CustomerIn, _=Depends(staff_only), db: Session = Depends(get_db)):
    return _upsert(user_id, data, db)


@app.delete("/customers/{user_id}", status_code=204)
def delete_customer(user_id: int, _=Depends(staff_only), db: Session = Depends(get_db)):
    c = db.query(Customer).filter_by(user_id=user_id).first()
    if not c:
        raise HTTPException(404, "Customer not found")
    db.delete(c); db.commit()


@app.get("/health")
def health():
    return {"service": "customer", "status": "ok"}
