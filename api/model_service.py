"""P5 (M4) — โหลดโมเดล champion + เตรียม feature สำหรับ serving (ใช้ทั้ง API real-time และ batch)

หลักการกัน Training–Serving Skew:
    - feature ทั้งหมดสร้างด้วย `src.features.build_features` ตัวเดียวกับตอน train
    - ลำดับคอลัมน์ใช้ `feature_list.json` ที่ train.py log ไว้ใน run ของโมเดล
    - ส่งประวัติ "ทุกสินค้า" เข้า build_features พร้อมกัน เพื่อให้ item_encoded ตรงกับตอน train

p50 / p_q สำหรับ q ใดก็ได้ (newsvendor ต้องใช้ q ที่เปลี่ยนตามราคา/ต้นทุน):
    F_q = ŷ + quantile_q(residual)  โดย residual = y - ŷ บนช่วง validation (โมเดลไม่เคยเห็น)
    → ปรับเทียบ (calibrate) ได้ทุก q จากโมเดลเดียว ไม่ต้องเทรนโมเดลแยกทุก quantile

รัน batch (พยากรณ์ "วันถัดจากข้อมูลล่าสุด" ทุกสินค้า → data/processed/predictions/):
    python -m api.model_service
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import ROOT, load_config
from src.features import build_features

log = logging.getLogger("model_service")

QUANTILE_GRID = np.round(np.arange(0.05, 0.951, 0.05), 2)
MAX_LAG = 14  # ต้องมีประวัติอย่างน้อยเท่า lag ที่ยาวที่สุด
MIN_RESID_ROWS = 20  # จำนวนวันขั้นต่ำต่อสินค้าที่จะคำนวณ residual แยก
ALL = "__all__"


@dataclass
class ModelService:
    """เก็บโมเดล + ตาราง feature ที่คำนวณล่วงหน้า → ตอบ request ได้เร็ว (lookup + predict 1 แถว)"""

    model: object = None
    model_version: str | None = None
    run_id: str | None = None
    feature_columns: list[str] = field(default_factory=list)
    features: pd.DataFrame | None = None       # index = (date, article)
    yhat: dict = field(default_factory=dict)    # (date, article) → ค่าทำนายของโมเดล (คำนวณล่วงหน้า)
    residual_q: dict[str, dict[float, float]] = field(default_factory=dict)  # article/ALL → {q: resid}
    articles: list[str] = field(default_factory=list)
    min_date: pd.Timestamp | None = None
    max_date: pd.Timestamp | None = None        # วันที่ล่าสุดที่ทำนายได้ (= วันถัดจากข้อมูลจริงวันสุดท้าย)
    error: str | None = None

    @property
    def ready(self) -> bool:
        return self.model is not None and self.features is not None

    # ---------- โหลด ----------
    @classmethod
    def from_registry(cls, cfg: dict | None = None, alias: str = "champion") -> ModelService:
        """โหลด models:/<name>@champion จาก MLflow + history จาก parquet; ถ้าพังคืน service ที่ ready=False"""
        import mlflow

        from src import registry

        cfg = cfg or load_config()
        svc = cls()
        try:
            client = registry.get_client(cfg)
            name = registry.model_name(cfg)
            mv = client.get_model_version_by_alias(name, alias)
            mlflow.set_tracking_uri(registry.tracking_uri(cfg))
            model = mlflow.pyfunc.load_model(f"models:/{name}@{alias}")
            feature_columns = json.loads(mlflow.artifacts.load_text(f"runs:/{mv.run_id}/feature_list.json"))
            history = load_history(cfg)
            svc.setup(model, feature_columns, history, cfg)
            svc.model_version, svc.run_id = str(mv.version), mv.run_id
            log.info("loaded %s v%s (run %s), %d articles, predict range %s..%s", name, mv.version,
                     mv.run_id[:8], len(svc.articles), svc.min_date.date(), svc.max_date.date())
        except Exception as exc:  # API ต้องเปิดได้แม้ยังไม่มีโมเดล → /health บอกสถานะ
            svc.error = f"{type(exc).__name__}: {exc}"
            log.error("load model failed: %s", svc.error)
        return svc

    def setup(self, model, feature_columns: list[str], history: pd.DataFrame, cfg: dict) -> None:
        """สร้างตาราง feature ล่วงหน้า + residual quantile จากช่วง validation"""
        history = history[["date", "article", "qty"]].copy()
        history["date"] = pd.to_datetime(history["date"])
        last = history["date"].max()
        self.articles = sorted(history["article"].unique().tolist())

        # เพิ่มแถว "พรุ่งนี้" (qty ยังไม่รู้ = NaN) ให้ทุกสินค้า → build_features คำนวณ lag/rolling จากอดีตให้
        next_day = last + pd.Timedelta(days=1)
        tomorrow = pd.DataFrame({"date": next_day, "article": self.articles, "qty": np.nan})
        full = pd.concat([history, tomorrow], ignore_index=True)
        feats = build_features(full, lags=tuple(cfg["features"]["lags"]),
                               windows=tuple(cfg["features"]["rolling_windows"]))
        feats["date"] = pd.to_datetime(feats["date"])

        self.model = model
        self.feature_columns = list(feature_columns)
        self.features = feats.set_index(["date", "article"]).sort_index()
        self.min_date = history["date"].min() + pd.Timedelta(days=MAX_LAG)
        self.max_date = last + pd.Timedelta(days=1)

        # ทำนายทุก (date, article) ที่ feature ครบในครั้งเดียว → request จริงเป็นแค่ lookup (เร็ว, p95 ต่ำ)
        ready = self.features[self.features.index.get_level_values("date") >= self.min_date]
        ready = ready.dropna(subset=self.feature_columns)
        self.yhat = dict(zip(ready.index, self._raw_predict(ready), strict=True))

        # residual บน validation: (train_end, val_end] — ช่วงที่โมเดลไม่ได้ใช้เทรน
        val = feats[(feats["date"] > cfg["split"]["train_end"]) & (feats["date"] <= cfg["split"]["val_end"])]
        val = val.dropna(subset=self.feature_columns + ["qty"]).copy()
        val["resid"] = val["qty"].to_numpy(float) - self._raw_predict(val) if len(val) else []

        def grid(resid) -> dict[float, float]:
            resid = np.asarray(resid, float) if len(resid) else np.zeros(1)  # ไม่มีข้อมูล → p_q = ŷ
            return {float(q): float(np.quantile(resid, q)) for q in QUANTILE_GRID}

        # แยกรายสินค้า เพราะสินค้าขายเยอะคลาดเคลื่อน (เป็นชิ้น) มากกว่าสินค้าขายน้อย; ข้อมูลน้อยใช้ค่ารวม
        self.residual_q = {ALL: grid(val["resid"])}
        for article, g in val.groupby("article"):
            if len(g) >= MIN_RESID_ROWS:
                self.residual_q[article] = grid(g["resid"])

    # ---------- ทำนาย ----------
    def _raw_predict(self, rows: pd.DataFrame) -> np.ndarray:
        pred = self.model.predict(rows[self.feature_columns])
        return np.asarray(pred, dtype=float).ravel()

    def residual_at(self, q: float, article: str | None = None) -> float:
        """interpolate residual quantile ที่ q ของสินค้านั้น (clip ไว้ในช่วง 0.05–0.95)"""
        table = self.residual_q.get(article) or self.residual_q[ALL]
        qs = np.array(sorted(table))
        return float(np.interp(np.clip(q, qs[0], qs[-1]), qs, [table[k] for k in qs]))

    def check_input(self, article: str, date) -> str | None:
        """คืนข้อความ error ถ้า article/date ใช้ไม่ได้ (API แปลงเป็น 422)"""
        if article not in self.articles:
            return f"unknown article '{article}' (มี {len(self.articles)} สินค้า ดูได้ที่ GET /articles)"
        d = pd.Timestamp(date)
        if d < self.min_date or d > self.max_date:
            return (f"date {d.date()} อยู่นอกช่วงที่ทำนายได้ {self.min_date.date()}..{self.max_date.date()} "
                    "(ทำนายได้ไกลสุด 1 วันหลังข้อมูลล่าสุด)")
        if (d, article) not in self.yhat:
            return f"date {d.date()}: ประวัติยอดขายของ '{article}' ไม่พอสร้าง feature"
        return None

    def predict(self, article: str, date, q: float) -> dict:
        """คืน p50 และ p_q (ยอดขายติดลบไม่ได้ → clip ที่ 0)"""
        yhat = float(self.yhat[(pd.Timestamp(date), article)])
        p50 = max(0.0, yhat + self.residual_at(0.5, article))
        p_q = max(0.0, yhat + self.residual_at(q, article))
        return {"p50": round(p50, 2), "p_q": round(p_q, 2)}

    def batch_predict(self, date=None, q: float = 0.5) -> pd.DataFrame:
        """พยากรณ์ทุกสินค้าของวันเดียว (ค่าเริ่มต้น = พรุ่งนี้) — ใช้ใน Prefect flow ตอนกลางคืน"""
        date = pd.Timestamp(date) if date is not None else self.max_date
        out = [{"date": date.date().isoformat(), "article": a, **self.predict(a, date, q), "q": q,
                "model_version": self.model_version} for a in self.articles]
        return pd.DataFrame(out)


def load_history(cfg: dict) -> pd.DataFrame:
    """ประวัติยอดขายรายวัน (date, article, qty) จาก parquet ที่ ingest/train สร้าง"""
    path = Path(os.environ.get("HISTORY_PATH", ROOT / cfg["paths"]["processed"]))
    if not path.exists():
        raise FileNotFoundError(f"ไม่พบ {path} — รัน pipeline (ingest/train) ก่อน")
    return pd.read_parquet(path)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    cfg = load_config()
    svc = ModelService.from_registry(cfg)
    if not svc.ready:
        raise SystemExit(f"โหลดโมเดลไม่ได้: {svc.error}")
    df = svc.batch_predict(q=cfg["model"]["quantile_default"])
    out = ROOT / "data" / "processed" / "predictions" / f"{df['date'].iloc[0]}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(df.to_string(index=False))
    print(f"\nบันทึก {out}")


if __name__ == "__main__":
    main()
