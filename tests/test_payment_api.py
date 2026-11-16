import pytest
import sys
import os
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app")))

from main import app

@pytest.fixture
def client():
    return TestClient(app)

def test_index_endpoint(client):
    res = client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert data["service"] == "cloud-native-payment-gateway"
    assert data["gitops_managed_by"] == "ArgoCD"

def test_healthz(client):
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.json()["status"] == "alive"

def test_readyz(client):
    res = client.get("/readyz")
    assert res.status_code == 200
    assert res.json()["can_accept_transactions"] is True

def test_process_charge_approved(client):
    payload = {
        "amount": 75.25,
        "currency": "USD",
        "customer_id": "cust_4421",
        "card_token": "tok_visa_valid"
    }
    res = client.post("/v1/charge", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "APPROVED"
    assert data["amount"] == 75.25
    assert data["id"].startswith("txn_")

def test_process_charge_declined_large_amount(client):
    payload = {
        "amount": 99999.0, # Exceeds 50k threshold
        "currency": "USD",
        "customer_id": "cust_fraud",
        "card_token": "tok_risk"
    }
    res = client.post("/v1/charge", json=payload)
    assert res.status_code == 400

def test_get_transactions(client):
    res = client.get("/v1/transactions")
    assert res.status_code == 200
    assert res.json()["count"] >= 1

def test_metrics(client):
    client.get("/healthz")
    res = client.get("/metrics")
    assert res.status_code == 200
    assert "payment_transactions_total" in res.text
    assert "app_version_info" in res.text
