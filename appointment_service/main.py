import os, datetime as dt
from typing import Optional
import httpx
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Mapped, mapped_column, Session
from common import Base, engine, get_db, current_user, staff_only, oauth2

PET_URL = os.getenv("PET_URL", "http://localhost:8003")
CATALOG_URL = os.getenv("CATALOG_URL", "http://localhost:8004")
SLOT_CAPACITY = int(os.getenv("SLOT_CAPACITY", "3"))   # max bookings at the same time
STATUSES = {"booked", "in_progress", "completed", "cancelled"}


class Appointment(Base):
    __tablename__ = "appointments"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(index=True)
    pet_id: Mapped[int]
    service_id: Mapped[int]
    service_name: Mapped[str]          # snapshot, so reports don't need the catalog
    price: Mapped[float]               # snapshot of price at booking time
    scheduled_at: Mapped[dt.datetime]
    status: Mapped[str] = mapped_column(default="booked")
    notes: Mapped[str] = mapped_column(default="")


Base.metadata.create_all(engine)
app = FastAPI(title="Happy Tails - Appointments Service")


class AppointmentIn(BaseModel):
    pet_id: int
    service_id: int
    scheduled_at: dt.datetime
    notes: str = ""


class AppointmentOut(BaseModel):
    id: int
    owner_id: int
    pet_id: int
    service_id: int
    service_name: str
    price: float
    scheduled_at: dt.datetime
    status: str
    notes: str
    model_config = {"from_attributes": True}


class StatusIn(BaseModel):
    status: str


def fetch(url: str, token: str, what: str):
    """Call another microservice, forwarding the user's JWT."""
    try:
        r = httpx.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=5)
    except httpx.HTTPError:
        raise HTTPException(503, f"{what} service is unavailable")
    if r.status_code == 404:
        raise HTTPException(404, f"{what} not found")
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.json().get("detail", f"{what} service error"))
    return r.json()


def _get_allowed(appt_id: int, user: dict, db: Session) -> Appointment:
    a = db.get(Appointment, appt_id)
    if not a:
        raise HTTPException(404, "Appointment not found")
    if user["role"] == "owner" and a.owner_id != user["id"]:
        raise HTTPException(403, "Not your appointment")
    return a


@app.post("/appointments", response_model=AppointmentOut, status_code=201)
def book(data: AppointmentIn, user=Depends(current_user), token: str = Depends(oauth2), db: Session = Depends(get_db)):
    pet = fetch(f"{PET_URL}/pets/{data.pet_id}", token, "Pet")           # 403 if not owner's pet
    svc = fetch(f"{CATALOG_URL}/services/{data.service_id}", token, "Service")
    if not svc["active"]:
        raise HTTPException(400, "This service is no longer available")

    when = data.scheduled_at.replace(tzinfo=None)
    if when <= dt.datetime.now():
        raise HTTPException(400, "Appointment must be in the future")

    active = db.query(Appointment).filter(Appointment.scheduled_at == when, Appointment.status != "cancelled")
    if active.filter(Appointment.pet_id == pet["id"]).first():
        raise HTTPException(409, "This pet already has an appointment at that time")
    if active.count() >= SLOT_CAPACITY:
        raise HTTPException(409, "That time slot is full, please choose another")

    appt = Appointment(owner_id=pet["owner_id"], pet_id=pet["id"], service_id=svc["id"],
                       service_name=svc["name"], price=svc["price"], scheduled_at=when, notes=data.notes)
    db.add(appt); db.commit(); db.refresh(appt)
    return appt


@app.get("/appointments", response_model=list[AppointmentOut])
def list_appointments(status: Optional[str] = None, on_date: Optional[dt.date] = None,
                      user=Depends(current_user), db: Session = Depends(get_db)):
    """Owners see their own; staff see everything (use on_date for the daily schedule)."""
    q = db.query(Appointment)
    if user["role"] == "owner":
        q = q.filter(Appointment.owner_id == user["id"])
    if status:
        q = q.filter(Appointment.status == status)
    if on_date:
        start = dt.datetime.combine(on_date, dt.time.min)
        q = q.filter(Appointment.scheduled_at >= start, Appointment.scheduled_at < start + dt.timedelta(days=1))
    return q.order_by(Appointment.scheduled_at).all()


@app.get("/appointments/{appt_id}", response_model=AppointmentOut)
def get_appointment(appt_id: int, user=Depends(current_user), db: Session = Depends(get_db)):
    return _get_allowed(appt_id, user, db)


@app.patch("/appointments/{appt_id}/status", response_model=AppointmentOut)
def update_status(appt_id: int, data: StatusIn, _=Depends(staff_only), db: Session = Depends(get_db)):
    if data.status not in STATUSES:
        raise HTTPException(400, f"status must be one of {sorted(STATUSES)}")
    a = db.get(Appointment, appt_id)
    if not a:
        raise HTTPException(404, "Appointment not found")
    a.status = data.status
    db.commit(); db.refresh(a)
    return a


@app.delete("/appointments/{appt_id}", response_model=AppointmentOut)
def cancel(appt_id: int, user=Depends(current_user), db: Session = Depends(get_db)):
    a = _get_allowed(appt_id, user, db)
    if a.status in ("completed", "cancelled"):
        raise HTTPException(400, f"Cannot cancel a {a.status} appointment")
    a.status = "cancelled"
    db.commit(); db.refresh(a)
    return a


@app.get("/health")
def health():
    return {"service": "appointments", "status": "ok"}
