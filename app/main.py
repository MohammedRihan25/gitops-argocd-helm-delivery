import os
import time
import socket
import logging
import json
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, Field

# Structured JSON logging
class JSONLogFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "environment": os.getenv("APP_ENV", "dev"),
            "version": os.getenv("APP_VERSION", "1.0.0"),
            "pod": socket.gethostname(),
        })

logger = logging.getLogger("payment-gateway")
handler = logging.StreamHandler()
handler.setFormatter(JSONLogFormatter())
logger.addHandler(handler)
logger.setLevel(logging.INFO)

app = FastAPI(
    title="Cloud-Native Payment Gateway",
    description="Mission-critical transaction microservice managed via GitOps, Helm, and ArgoCD",
    version=os.getenv("APP_VERSION", "1.0.0"),
)

METRICS = {
    "transactions_total": 0,
    "transactions_successful": 0,
    "transactions_declined": 0,
    "amount_total_usd": 0.0,
    "requests_by_endpoint": {},
}

TRANSACTIONS_STORE = [
    {
        "id": "txn_1001",
        "amount": 129.50,
        "currency": "USD",
        "customer_id": "cust_9921",
        "status": "APPROVED",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
]

class ChargeRequest(BaseModel):
    amount: float = Field(..., gt=0.0, description="Transaction amount in USD")
    currency: str = Field(default="USD", pattern="^[A-Z]{3}$")
    customer_id: str = Field(..., min_length=3)
    card_token: str = Field(..., min_length=4)

@app.middleware("http")
async def track_latency(request: Request, call_next):
    start = time.time()
    path = request.url.path
    METRICS["requests_by_endpoint"][path] = METRICS["requests_by_endpoint"].get(path, 0) + 1
    response = await call_next(request)
    duration = time.time() - start
    logger.info(f"{request.method} {path} handled in {duration:.4f}s with status {response.status_code}")
    return response

@app.get("/")
def index():
    return {
        "service": "cloud-native-payment-gateway",
        "environment": os.getenv("APP_ENV", "dev"),
        "version": os.getenv("APP_VERSION", "1.0.0"),
        "gitops_managed_by": "ArgoCD",
        "pod_name": socket.gethostname(),
        "docs": "/docs",
    }

@app.get("/healthz")
def healthz():
    return {
        "status": "alive",
        "pod": socket.gethostname(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

@app.get("/readyz")
def readyz():
    return {
        "status": "ready",
        "environment": os.getenv("APP_ENV", "dev"),
        "can_accept_transactions": True,
    }

@app.post("/v1/charge", status_code=201)
def process_charge(charge: ChargeRequest):
    METRICS["transactions_total"] += 1
    
    # Simple simulated decline rule for testing canary rollouts
    if charge.amount > 50000.0:
        METRICS["transactions_declined"] += 1
        raise HTTPException(status_code=400, detail="Transaction amount exceeds safety threshold")

    txn_id = f"txn_{int(time.time() * 1000)}"
    record = {
        "id": txn_id,
        "amount": charge.amount,
        "currency": charge.currency,
        "customer_id": charge.customer_id,
        "status": "APPROVED",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    TRANSACTIONS_STORE.append(record)
    METRICS["transactions_successful"] += 1
    METRICS["amount_total_usd"] += charge.amount

    logger.info(f"Transaction approved: {txn_id} for ${charge.amount} ({charge.customer_id})")
    return record

@app.get("/v1/transactions")
def get_transactions():
    return {
        "environment": os.getenv("APP_ENV", "dev"),
        "count": len(TRANSACTIONS_STORE),
        "transactions": TRANSACTIONS_STORE[-10:],
    }

@app.get("/metrics")
def get_metrics():
    lines = [
        "# HELP payment_transactions_total Total transactions processed.",
        "# TYPE payment_transactions_total counter",
        f'payment_transactions_total {METRICS["transactions_total"]}',
        "# HELP payment_transactions_successful_total Total successful charges.",
        "# TYPE payment_transactions_successful_total counter",
        f'payment_transactions_successful_total {METRICS["transactions_successful"]}',
        "# HELP payment_amount_total_usd Total volume processed in USD.",
        "# TYPE payment_amount_total_usd counter",
        f'payment_amount_total_usd {METRICS["amount_total_usd"]:.2f}',
        "# HELP app_version_info GitOps application release info.",
        "# TYPE app_version_info gauge",
        f'app_version_info{{version="{os.getenv("APP_VERSION", "1.0.0")}",env="{os.getenv("APP_ENV", "dev")}",pod="{socket.gethostname()}"}} 1',
    ]
    for path, count in METRICS["requests_by_endpoint"].items():
        lines.append(f'payment_endpoint_requests_total{{path="{path}"}} {count}')
    return Response(content="\n".join(lines) + "\n", media_type="text/plain")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=False)
