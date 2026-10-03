"""P5 (M4) — FastAPI: /predict /recommend /health /metrics"""
from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from api.schemas import PredictRequest, RecommendRequest

app = FastAPI(title="Bakery Demand API", version="0.1.0")

REQUESTS = Counter("requests_total", "Total requests", ["endpoint", "status"])
LATENCY = Histogram("request_latency_seconds", "Request latency", ["endpoint"])

MODEL_VERSION = None  # TODO(M4): โหลด champion จาก MLflow registry ตอน startup


@app.get("/health")
def health():
    return {"status": "ok", "model_version": MODEL_VERSION}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/predict")
def predict(req: PredictRequest):
    # TODO(M4): ดึงประวัติยอดขาย → src.features.build_features → model.predict
    raise NotImplementedError


@app.post("/recommend")
def recommend(req: RecommendRequest):
    # TODO(M4): predict quantile q จาก src.recommend.critical_ratio → recommended_qty
    raise NotImplementedError
