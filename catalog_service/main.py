from typing import Optional
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Mapped, mapped_column, Session
from common import Base, SessionLocal, engine, get_db, current_user, staff_only


class Service(Base):
    __tablename__ = "services"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    description: Mapped[str] = mapped_column(default="")
    price: Mapped[float]
    duration_minutes: Mapped[int] = mapped_column(default=60)
    active: Mapped[bool] = mapped_column(default=True)


Base.metadata.create_all(engine)

# seed a few default services on first run
with SessionLocal() as _db:
    if _db.query(Service).count() == 0:
        _db.add_all([
            Service(name="Full Grooming", description="Bath, haircut, nail trim", price=1200, duration_minutes=90),
            Service(name="Bath & Brush", description="Bath and coat brushing", price=600, duration_minutes=45),
            Service(name="Nail Trimming", description="Nail clipping and filing", price=250, duration_minutes=20),
            Service(name="Vet Check-up", description="General health examination", price=800, duration_minutes=30),
            Service(name="Pet Boarding (per day)", description="Day care and boarding", price=700, duration_minutes=1440),
        ])
        _db.commit()

app = FastAPI(title="Happy Tails - Services Catalog Service")


class ServiceIn(BaseModel):
    name: str
    description: str = ""
    price: float
    duration_minutes: int = 60
    active: bool = True


class ServiceOut(ServiceIn):
    id: int
    model_config = {"from_attributes": True}


@app.get("/services", response_model=list[ServiceOut])
def list_services(include_inactive: bool = False, _=Depends(current_user), db: Session = Depends(get_db)):
    q = db.query(Service)
    if not include_inactive:
        q = q.filter(Service.active.is_(True))
    return q.order_by(Service.name).all()


@app.get("/services/{service_id}", response_model=ServiceOut)
def get_service(service_id: int, _=Depends(current_user), db: Session = Depends(get_db)):
    s = db.get(Service, service_id)
    if not s:
        raise HTTPException(404, "Service not found")
    return s


@app.post("/services", response_model=ServiceOut, status_code=201)
def create_service(data: ServiceIn, _=Depends(staff_only), db: Session = Depends(get_db)):
    if db.query(Service).filter_by(name=data.name).first():
        raise HTTPException(409, "Service name already exists")
    s = Service(**data.model_dump())
    db.add(s); db.commit(); db.refresh(s)
    return s


@app.put("/services/{service_id}", response_model=ServiceOut)
def update_service(service_id: int, data: ServiceIn, _=Depends(staff_only), db: Session = Depends(get_db)):
    s = db.get(Service, service_id)
    if not s:
        raise HTTPException(404, "Service not found")
    for k, v in data.model_dump().items():
        setattr(s, k, v)
    db.commit(); db.refresh(s)
    return s


@app.delete("/services/{service_id}", status_code=204)
def deactivate_service(service_id: int, _=Depends(staff_only), db: Session = Depends(get_db)):
    """Soft delete so past appointments/reports stay valid."""
    s = db.get(Service, service_id)
    if not s:
        raise HTTPException(404, "Service not found")
    s.active = False
    db.commit()


@app.get("/health")
def health():
    return {"service": "catalog", "status": "ok"}
