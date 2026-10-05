"""P5 (M4) — load test: make loadtest → p50/p95/RPS ใน docs/evidence/loadtest_stats.csv

ผู้ใช้จำลองถามยอดขาย (predict) 3 ส่วน และขอจำนวนที่ควรเตรียม (recommend) 1 ส่วน
สุ่มสินค้าจาก GET /articles และวันที่จากช่วงที่ทำนายได้ใน GET /health
"""
import random
from datetime import date, timedelta

from locust import HttpUser, between, task


class BakeryUser(HttpUser):
    wait_time = between(0.1, 0.5)

    def on_start(self):
        self.articles = self.client.get("/articles").json()["articles"]
        start, end = self.client.get("/health").json()["predict_range"]
        last = date.fromisoformat(end)
        first = max(date.fromisoformat(start), last - timedelta(days=60))
        self.dates = [(first + timedelta(days=i)).isoformat() for i in range((last - first).days + 1)]

    def body(self) -> dict:
        return {"article": random.choice(self.articles), "date": random.choice(self.dates)}

    @task(3)
    def predict(self):
        self.client.post("/predict", json=self.body())

    @task(1)
    def recommend(self):
        price = round(random.uniform(0.9, 4.0), 2)
        self.client.post("/recommend", json={
            **self.body(), "on_hand": random.randint(0, 20),
            "unit_price": price, "unit_cost": round(price * random.uniform(0.2, 0.6), 2),
        })
