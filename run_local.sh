#!/usr/bin/env bash
# Run all services without Docker:  pip install -r auth_service/requirements.txt  then  ./run_local.sh
set -e
start() { (cd "$1" && uvicorn main:app --port "$2" &) ; }
start auth_service 8001
start customer_service 8002
start pet_service 8003
start catalog_service 8004
start appointment_service 8005
start report_service 8006
echo "Docs: http://localhost:8001/docs ... http://localhost:8006/docs"
wait
