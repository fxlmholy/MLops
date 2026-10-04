"""P5 — API: ตอบถูกกับ input ปกติ, 422 กับ input ผิดปกติ (ไม่ใช่ 500), 503 เมื่อยังไม่มีโมเดล

ใช้ ModelService ปลอม (โมเดล = lag_7) จึงไม่ต้องเปิด MLflow
"""
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.model_service import ALL, QUANTILE_GRID, ModelService
from src.config import load_config

ARTICLES = ["BAGUETTE", "CROISSANT"]
FEATURES = ["lag_7"]


class Lag7Model:
    """โมเดลจำลอง: ทำนายเท่ากับยอดวันเดียวกันสัปดาห์ก่อน"""

    def predict(self, X):
        return X["lag_7"].to_numpy(float)


def fake_service() -> ModelService:
    dates = pd.date_range("2022-08-01", "2022-09-30")
    idx = pd.MultiIndex.from_product([dates, ARTICLES], names=["date", "article"])
    feats = pd.DataFrame({"lag_7": 10.0}, index=idx)
    return ModelService(
        model=Lag7Model(), model_version="3", run_id="abc", feature_columns=FEATURES, features=feats,
        yhat=dict(zip(feats.index, Lag7Model().predict(feats), strict=True)),
        residual_q={ALL: {float(q): float((q - 0.5) * 10) for q in QUANTILE_GRID}},  # p50 = ŷ, p90 = ŷ+4
        articles=ARTICLES, min_date=dates[0], max_date=dates[-1],
    )


@pytest.fixture
def client():
    app.state.service = fake_service()
    with TestClient(app) as c:
        yield c
    app.state.service = None


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["model_version"] == "3"


def test_predict_ok(client):
    r = client.post("/predict", json={"article": "BAGUETTE", "date": "2022-09-15"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["p50"] == pytest.approx(10.0)
    assert body["p_q"] == pytest.approx(10 + (load_config()["model"]["quantile_default"] - 0.5) * 10)
    assert body["model_version"] == "3"
    assert "x-request-id" in r.headers


def test_recommend_newsvendor(client):
    # q = (1.0 - 0.2) / 1.0 = 0.8 → F_0.8 = 10 + 3 = 13 → เตรียม 13 - 4 = 9
    r = client.post("/recommend", json={"article": "CROISSANT", "date": "2022-09-15",
                                        "on_hand": 4, "unit_price": 1.0, "unit_cost": 0.2})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["q"] == pytest.approx(0.8)
    assert body["forecast"] == pytest.approx(13.0)
    assert body["recommended_qty"] == 9


def test_recommend_no_margin_prepares_nothing(client):
    r = client.post("/recommend", json={"article": "CROISSANT", "date": "2022-09-15",
                                        "on_hand": 0, "unit_price": 1.0, "unit_cost": 1.0})
    assert r.status_code == 200 and r.json()["recommended_qty"] == 0


@pytest.mark.parametrize("body", [
    {"article": "BAGUETTE", "date": "not-a-date", "on_hand": 1, "unit_price": 1, "unit_cost": 0.5},
    {"article": "BAGUETTE", "date": "2022-09-15", "on_hand": -1, "unit_price": 1, "unit_cost": 0.5},
    {"article": "BAGUETTE", "date": "2022-09-15", "on_hand": 1, "unit_price": -1, "unit_cost": 0.5},
    {"article": "BAGUETTE", "date": "2022-09-15", "on_hand": 1, "unit_price": 1, "unit_cost": 5},
    {"article": "BAGUETTE", "date": "2022-09-15", "on_hand": "abc", "unit_price": 1, "unit_cost": 0.5},
    {"article": "BAGUETTE", "date": "2022-09-15", "on_hand": 1.5, "unit_price": 1, "unit_cost": 0.5},
    {"date": "2022-09-15", "on_hand": 1, "unit_price": 1, "unit_cost": 0.5},              # field หาย
    {"article": "", "date": "2022-09-15", "on_hand": 1, "unit_price": 1, "unit_cost": 0.5},
    {"article": "PIZZA", "date": "2022-09-15", "on_hand": 1, "unit_price": 1, "unit_cost": 0.5},  # ไม่รู้จัก
    {"article": "BAGUETTE", "date": "2030-01-01", "on_hand": 1, "unit_price": 1, "unit_cost": 0.5},  # ไกลเกิน
    {"article": "BAGUETTE", "date": "2020-01-01", "on_hand": 1, "unit_price": 1, "unit_cost": 0.5},  # เก่าเกิน
    {"article": "BAGUETTE", "date": "2022-09-15", "on_hand": 1, "unit_price": 1, "unit_cost": 0.5,
     "hack": 1},                                                                          # field แปลก
])
def test_bad_recommend_inputs_return_422(client, body):
    assert client.post("/recommend", json=body).status_code == 422


@pytest.mark.parametrize("body", [
    {"article": "BAGUETTE"}, {"date": "2022-09-15"}, {"article": 123, "date": "2022-09-15"},
    {"article": "BAGUETTE", "date": "15/09/2022"}, {"article": "PIZZA", "date": "2022-09-15"},
])
def test_bad_predict_inputs_return_422(client, body):
    assert client.post("/predict", json=body).status_code == 422


def test_invalid_json_returns_422(client):
    r = client.post("/predict", content="{not json", headers={"content-type": "application/json"})
    assert r.status_code == 422


def test_no_model_returns_503():
    app.state.service = ModelService(error="no champion")
    with TestClient(app) as c:
        assert c.get("/health").json()["status"] == "degraded"
        assert c.post("/predict", json={"article": "BAGUETTE", "date": "2022-09-15"}).status_code == 503
    app.state.service = None


def test_metrics_exposed(client):
    client.post("/predict", json={"article": "BAGUETTE", "date": "2022-09-15"})
    text = client.get("/metrics").text
    assert "requests_total" in text and "request_latency_seconds" in text


def test_setup_uses_build_features():
    """ModelService.setup สร้าง feature ด้วย src.features.build_features ตัวเดียวกับ train"""
    cfg = load_config()
    dates = pd.date_range("2022-05-01", "2022-09-30")
    rng = np.random.default_rng(42)
    hist = pd.DataFrame([(d, a, int(rng.poisson(20))) for d in dates for a in ARTICLES],
                        columns=["date", "article", "qty"])
    svc = ModelService()
    try:
        svc.setup(Lag7Model(), FEATURES, hist, cfg)
    except NotImplementedError:
        pytest.skip("build_features ยังไม่ถูก merge (P3)")
    assert svc.max_date == pd.Timestamp("2022-10-01")       # พรุ่งนี้ของข้อมูลล่าสุด
    tomorrow = svc.features.loc[(pd.Timestamp("2022-10-01"), "BAGUETTE"), "lag_7"]
    assert tomorrow == hist[(hist.date == "2022-09-24") & (hist.article == "BAGUETTE")]["qty"].iloc[0]
    assert svc.residual_at(0.9, "BAGUETTE") >= svc.residual_at(0.5, "BAGUETTE")
    assert "BAGUETTE" in svc.residual_q  # มี residual แยกรายสินค้า
