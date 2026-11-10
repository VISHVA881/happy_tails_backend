# Happy Tails Pet Care Portal - FastAPI Microservices

| Service              | Port | Module           |
|----------------------|------|------------------|
| auth_service         | 8001 | Login            |
| customer_service     | 8002 | Customer Records |
| pet_service          | 8003 | Pet Profiles     |
| catalog_service      | 8004 | Services         |
| appointment_service  | 8005 | Appointments     |
| report_service       | 8006 | Reports          |

Run with Docker:  `docker compose up --build`
Run locally:      `pip install -r auth_service/requirements.txt && ./run_local.sh`
Swagger docs for each service: http://localhost:<port>/docs

Quick flow: register (owner) -> login -> PUT /customers/me -> POST /pets -> GET /services
-> POST /appointments -> staff: PATCH /appointments/{id}/status -> GET /reports/summary
(Staff register with role "staff" and staff_code "happytails-staff".)
