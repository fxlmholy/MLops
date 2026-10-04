"""P5 (M4) — FastAPI: /predict /recommend /health /metrics /articles /reload

- โหลดโมเดล alias `champion` จาก MLflow Registry ตอน startup (POST /reload หลัง promote/rollback)
- input ผิด → 422 (Pydantic + ตรวจ article/date กับข้อมูลจริง), ยังไม่มีโมเดล → 503
- ทุก request: log เป็น JSON 1 บรรทัด (request_id, latency, version, input, output) + Prometheus metrics
"""
import json
import logging
import sys
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

from api.model_service import ModelService
from api.schemas import PredictRequest, PredictResponse, RecommendRequest, RecommendResponse
from src.config import load_config
from src.recommend import critical_ratio, recommended_qty

CFG = load_config()
KNOWN_PATHS = {"/predict", "/recommend", "/health", "/metrics", "/articles", "/reload"}

REQUESTS = Counter("requests_total", "Total requests", ["endpoint", "status"])
LATENCY = Histogram("request_latency_seconds", "Request latency", ["endpoint"],
                    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.2, 0.5, 1, 2.5))
MODEL_LOADED = Gauge("model_loaded", "1 = มีโมเดล champion พร้อมให้บริการ")
MODEL_VERSION = Gauge("model_version", "เวอร์ชันของ champion ที่ใช้อยู่ (0 = ไม่มี)")

log = logging.getLogger("api")
if not log.handlers:
    _h = logging.StreamHandler(sys.stdout)
    _h.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(_h)
    log.setLevel(logging.INFO)
    log.propagate = False


def load_service() -> ModelService:
    svc = ModelService.from_registry(CFG)
    MODEL_LOADED.set(1 if svc.ready else 0)
    MODEL_VERSION.set(int(svc.model_version) if svc.model_version else 0)
    return svc


@asynccontextmanager
async def lifespan(app: FastAPI):
    # test ใส่ service ปลอมไว้ก่อนได้ → ไม่ต้องต่อ MLflow
    if getattr(app.state, "service", None) is None:
        app.state.service = load_service()
    yield


app = FastAPI(title="Bakery Demand API", version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def observe(request: Request, call_next):
    """วัด latency + นับ request + เขียน JSON log ทุก request"""
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    request.state.request_id = request_id
    request.state.log = {}
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["x-request-id"] = request_id
        return response
    finally:
        latency = time.perf_counter() - start
        endpoint = request.url.path if request.url.path in KNOWN_PATHS else "other"
        LATENCY.labels(endpoint).observe(latency)
        REQUESTS.labels(endpoint, str(status)).inc()
        if endpoint != "/metrics":
            svc = getattr(request.app.state, "service", None)
            log.info(json.dumps({
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "request_id": request_id,
                "method": request.method, "path": request.url.path, "status": status,
                "latency_ms": round(latency * 1000, 2),
                "model_version": getattr(svc, "model_version", None),
                **request.state.log,
            }, ensure_ascii=False, default=str))


def get_service(request: Request) -> ModelService:
    svc: ModelService = request.app.state.service
    if svc is None or not svc.ready:
        raise HTTPException(503, detail=f"ยังไม่มีโมเดล champion: {getattr(svc, 'error', None)}")
    return svc


def check(svc: ModelService, article: str, date) -> None:
    """article ไม่รู้จัก / date นอกช่วง → 422 (รูปแบบเดียวกับ error ของ Pydantic)"""
    msg = svc.check_input(article, date)
    if msg:
        field = "article" if msg.startswith("unknown article") else "date"
        raise HTTPException(422, detail=[{"loc": ["body", field], "msg": msg, "type": "value_error"}])


@app.get("/health")
def health(request: Request):
    svc = request.app.state.service
    ready = bool(svc and svc.ready)
    return {
        "status": "ok" if ready else "degraded",
        "model_loaded": ready,
        "model_version": svc.model_version if svc else None,
        "predict_range": [str(svc.min_date.date()), str(svc.max_date.date())] if ready else None,
        "error": None if ready else getattr(svc, "error", None),
    }


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/articles")
def articles(request: Request):
    return {"articles": get_service(request).articles}


@app.post("/reload")
def reload(request: Request):
    """โหลด champion ใหม่ (ใช้หลัง promote / rollback) — ถ้าโหลดไม่ได้ยังใช้ตัวเดิมต่อ"""
    new = load_service()
    if not new.ready:
        raise HTTPException(503, detail=f"reload failed, keep v{request.app.state.service.model_version}: "
                                        f"{new.error}")
    old = request.app.state.service.model_version
    request.app.state.service = new
    return {"status": "reloaded", "from_version": old, "to_version": new.model_version}


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest, request: Request):
    svc = get_service(request)
    check(svc, req.article, req.date)
    q = CFG["model"]["quantile_default"]
    out = {"article": req.article, "date": req.date, **svc.predict(req.article, req.date, q),
           "q": q, "model_version": svc.model_version}
    request.state.log = {"input": req.model_dump(mode="json"), "output": out}
    return out


@app.post("/recommend", response_model=RecommendResponse)
def recommend(req: RecommendRequest, request: Request):
    svc = get_service(request)
    check(svc, req.article, req.date)
    q = critical_ratio(req.unit_price, req.unit_cost)
    pred = svc.predict(req.article, req.date, max(q, 0.05))
    forecast = pred["p_q"] if q > 0 else 0.0  # ต้นทุน = ราคา → ไม่มีกำไร ไม่ควรเตรียมเพิ่ม
    out = {"article": req.article, "date": req.date, "forecast": forecast, "p50": pred["p50"],
           "q": round(q, 4), "on_hand": req.on_hand,
           "recommended_qty": recommended_qty(forecast, req.on_hand), "model_version": svc.model_version}
    request.state.log = {"input": req.model_dump(mode="json"), "output": out}
    return out
