import os
from collections import Counter, defaultdict
import httpx
from fastapi import FastAPI, Depends, HTTPException
from common import staff_only, oauth2

APPT_URL = os.getenv("APPT_URL", "http://localhost:8005")
CUSTOMER_URL = os.getenv("CUSTOMER_URL", "http://localhost:8002")
PET_URL = os.getenv("PET_URL", "http://localhost:8003")

app = FastAPI(title="Happy Tails - Reports Service")


def get(url: str, token: str, what: str):
    try:
        r = httpx.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=10)
    except httpx.HTTPError:
        raise HTTPException(503, f"{what} service is unavailable")
    if r.status_code >= 400:
        raise HTTPException(r.status_code, f"{what} service error")
    return r.json()


@app.get("/reports/summary")
def summary(_=Depends(staff_only), token: str = Depends(oauth2)):
    appts = get(f"{APPT_URL}/appointments", token, "Appointments")
    customers = get(f"{CUSTOMER_URL}/customers", token, "Customer")
    pets = get(f"{PET_URL}/pets", token, "Pet")
    by_status = Counter(a["status"] for a in appts)
    revenue = sum(a["price"] for a in appts if a["status"] == "completed")
    return {
        "total_customers": len(customers),
        "total_pets": len(pets),
        "total_appointments": len(appts),
        "appointments_by_status": dict(by_status),
        "completed_revenue": revenue,
    }


@app.get("/reports/popular-services")
def popular_services(limit: int = 5, _=Depends(staff_only), token: str = Depends(oauth2)):
    appts = get(f"{APPT_URL}/appointments", token, "Appointments")
    counts = Counter(a["service_name"] for a in appts if a["status"] != "cancelled")
    return [{"service": s, "bookings": n} for s, n in counts.most_common(limit)]


@app.get("/reports/revenue-by-day")
def revenue_by_day(_=Depends(staff_only), token: str = Depends(oauth2)):
    appts = get(f"{APPT_URL}/appointments?status=completed", token, "Appointments")
    daily = defaultdict(float)
    for a in appts:
        daily[a["scheduled_at"][:10]] += a["price"]
    return [{"date": d, "revenue": r} for d, r in sorted(daily.items())]


@app.get("/reports/top-customers")
def top_customers(limit: int = 5, _=Depends(staff_only), token: str = Depends(oauth2)):
    appts = get(f"{APPT_URL}/appointments", token, "Appointments")
    customers = {c["user_id"]: c["full_name"] for c in get(f"{CUSTOMER_URL}/customers", token, "Customer")}
    spend = defaultdict(float)
    for a in appts:
        if a["status"] == "completed":
            spend[a["owner_id"]] += a["price"]
    top = sorted(spend.items(), key=lambda x: x[1], reverse=True)[:limit]
    return [{"owner_id": o, "name": customers.get(o, "Unknown"), "total_spent": s} for o, s in top]


@app.get("/health")
def health():
    return {"service": "reports", "status": "ok"}
