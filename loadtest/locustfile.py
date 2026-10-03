"""P5 (M4) — make loadtest → รายงาน p50/p95/RPS ใน docs/evidence/loadtest_stats.csv"""
from locust import HttpUser, between, task


class BakeryUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task(3)
    def predict(self):
        self.client.post("/predict", json={"article": "TRADITIONAL BAGUETTE", "date": "2022-09-15"})

    @task(1)
    def recommend(self):
        self.client.post("/recommend", json={
            "article": "TRADITIONAL BAGUETTE", "date": "2022-09-15",
            "on_hand": 10, "unit_price": 1.2, "unit_cost": 0.4,
        })
