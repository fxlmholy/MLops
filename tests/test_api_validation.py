"""P5 — input ผิดปกติต้องได้ 422 ไม่ใช่ 500"""
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_bad_inputs_return_422():
    bad = [
        {"article": "BAGUETTE", "date": "not-a-date", "on_hand": 1, "unit_price": 1, "unit_cost": 0.5},
        {"article": "BAGUETTE", "date": "2022-09-15", "on_hand": -1, "unit_price": 1, "unit_cost": 0.5},
        {"article": "BAGUETTE", "date": "2022-09-15", "on_hand": 1, "unit_price": 1, "unit_cost": 5},
        {"date": "2022-09-15", "on_hand": 1, "unit_price": 1, "unit_cost": 0.5},
    ]
    for body in bad:
        assert client.post("/recommend", json=body).status_code == 422
