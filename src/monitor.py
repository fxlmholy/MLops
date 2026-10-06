"""P6 (M5) — Monitoring: Data Drift (PSI + Evidently) · Concept Drift (rolling WAPE_7d) · System · Retrain

แยกการเฝ้าระวังเป็น 3 ชั้น (เกณฑ์อยู่ใน configs/config.yaml → monitoring / slo):

    1) Data drift     P(X) เปลี่ยน     PSI ของ lag/สัดส่วนสินค้า (reference = ช่วง train, current = ล่าสุด) > 0.2
    2) Concept drift  P(y|X) เปลี่ยน   WAPE_7d (rolling 7 วัน) > 1.2 × WAPE ตอน deploy (ช่วง validation)
    3) System         API             p95 latency > 200 ms หรือ 5xx error rate > 1%  (จาก Prometheus)

นโยบาย retrain: ครบ 7 วันนับจากเทรนครั้งล่าสุด (schedule) **หรือ** มี alert ข้อใดข้อหนึ่ง
    → train → evaluate_gate (ผ่าน gate จึงขึ้น registry) → POST /reload ให้ API ใช้ champion ใหม่

รัน:
    python -m src.monitor                                # ทั้ง 3 scenario (normal / data_drift / concept_drift)
    python -m src.monitor --scenario concept_drift --retrain
    python -m src.monitor --data new_sales.parquet       # ใช้กับยอดขายจริงที่เข้ามาใหม่ (date, article, qty)
exit code (เฉพาะ --data): 0 = ไม่มี alert, 1 = มี alert (ใช้ใน cron ให้รู้ว่าต้องดู)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from src.config import ROOT, load_config
from src.features import build_features
from src.simulate_drift import SCENARIOS, default_start, simulate

log = logging.getLogger("monitor")

# feature ที่ใช้ตัดสิน data drift (alert) = lag ของยอดขาย ปรับเป็น "ดัชนียอดขาย" (÷ ค่าเฉลี่ยของสินค้านั้นในช่วง train)
#   - ไม่ใช้ rolling_mean/std: ค่าเรียบ + ต่อเนื่องกันวันต่อวัน (autocorrelated) ช่วง current สั้นแค่ ~30 วัน
#     → PSI สูงเกินจริงแม้ข้อมูลไม่เปลี่ยน (ทดสอบกับข้อมูลคงที่ได้ PSI ~1.0) จึงแสดงใน Evidently HTML อย่างเดียว
#   - ไม่ใช้ day_of_week/month/is_holiday: ช่วง current เป็นเดือนเดียว ปฏิทินจึง "เลื่อน" เสมอโดยไม่ผิดปกติ
#   - ÷ ค่าเฉลี่ยรายสินค้า: ยอดแต่ละสินค้าต่างกัน ~20 เท่า ถ้าไม่ปรับ ความต่างระหว่างสินค้ากลบการเปลี่ยนจริง
#   - ไม่ใช้ lag_14: ใน 14 วันล่าสุด lag_14 คือยอดของ 2 สัปดาห์ก่อนหน้า (ข้อมูลจริง ก.ย. = ช่วงหลังหน้าร้อน)
#     ทำให้ normal ได้ PSI 0.30 (เตือนผิด) ขณะที่ lag_1/lag_7 = 0.13/0.15
ALERT_FEATURES = ["lag_1", "lag_7"]
MONITORED_FEATURES = ALERT_FEATURES + ["lag_14", "rolling_mean_7", "rolling_mean_28", "rolling_std_7"]
EVIDENCE_DIR = ROOT / "docs" / "evidence"
REPORT_DIR = ROOT / "reports"  # html ของ Evidently ใหญ่ → อยู่ใน .gitignore (reports/*.html)
EPS = 1e-4


# ============================== 1) Data drift ==============================
def psi(reference, current, bins: int = 10) -> float:
    """Population Stability Index = Σ (cur% − ref%) × ln(cur% / ref%)

    แบ่ง bin ด้วย quantile ของ reference (แต่ละ bin มีข้อมูล ref ~10%) → ทนต่อค่าที่เบ้ เช่นยอดขาย
    อ่านค่า: < 0.1 คงที่ · 0.1–0.2 เริ่มเปลี่ยน · > 0.2 drift ชัดเจน
    """
    ref = np.asarray(reference, dtype=float)
    cur = np.asarray(current, dtype=float)
    ref, cur = ref[~np.isnan(ref)], cur[~np.isnan(cur)]
    if len(ref) == 0 or len(cur) == 0:
        return float("nan")
    edges = np.unique(np.quantile(ref, np.linspace(0, 1, bins + 1)))
    if len(edges) < 2:  # ค่าคงที่ทั้งคอลัมน์
        edges = np.array([ref[0] - 0.5, ref[0] + 0.5])
    edges[0], edges[-1] = -np.inf, np.inf
    ref_pct = np.histogram(ref, edges)[0] / len(ref)
    cur_pct = np.histogram(cur, edges)[0] / len(cur)
    return _psi_from_pct(ref_pct, cur_pct)


def categorical_psi(reference, current) -> float:
    """PSI ของตัวแปรกลุ่ม (สัดส่วนของแต่ละสินค้า) — จับการเปลี่ยน product mix"""
    ref = pd.Series(reference).value_counts(normalize=True)
    cur = pd.Series(current).value_counts(normalize=True)
    cats = ref.index.union(cur.index)
    return _psi_from_pct(ref.reindex(cats, fill_value=0).to_numpy(),
                         cur.reindex(cats, fill_value=0).to_numpy())


def _psi_from_pct(ref_pct, cur_pct) -> float:
    ref_pct = np.clip(ref_pct, EPS, None)  # กัน ln(0) เมื่อ bin ว่าง
    cur_pct = np.clip(cur_pct, EPS, None)
    return float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))


def demand_index(reference: pd.DataFrame, current: pd.DataFrame, col: str) -> tuple[pd.Series, pd.Series]:
    """ค่า feature ÷ ค่าเฉลี่ยของสินค้านั้นในช่วง reference (1.0 = ขายเท่าปกติของสินค้านั้น)"""
    scale = reference.groupby("article")[col].mean().replace(0, np.nan)
    return reference[col] / reference["article"].map(scale), current[col] / current["article"].map(scale)


def check_data_drift(reference: pd.DataFrame, current: pd.DataFrame, threshold: float,
                     columns: list[str] | None = None, weight_col: str = "qty") -> dict:
    """PSI ของดัชนียอดขาย (lag ÷ ค่าเฉลี่ยรายสินค้า) + PSI ของสัดส่วนยอดขายรายสินค้า → alert ถ้าตัวใด > threshold"""
    columns = columns or [c for c in ALERT_FEATURES if c in reference.columns]
    by_item = "article" in reference.columns and "article" in current.columns
    scores = {}
    for c in columns:
        ref, cur = demand_index(reference, current, c) if by_item else (reference[c], current[c])
        scores[c] = round(psi(ref, cur), 4)
    if by_item:
        # สัดส่วน "ยอดขาย" ของแต่ละสินค้า (ไม่ใช่จำนวนแถว เพราะทุกสินค้ามี 1 แถว/วันเท่ากัน)
        ref_mix = reference.groupby("article")[weight_col].sum()
        cur_mix = current.groupby("article")[weight_col].sum()
        cats = ref_mix.index.union(cur_mix.index)
        scores["article_mix"] = round(_psi_from_pct(
            (ref_mix.reindex(cats, fill_value=0) / max(ref_mix.sum(), EPS)).to_numpy(),
            (cur_mix.reindex(cats, fill_value=0) / max(cur_mix.sum(), EPS)).to_numpy()), 4)
    drifted = [c for c, v in scores.items() if v > threshold]
    return {
        "psi": scores,
        "max_psi": max(scores.values()) if scores else float("nan"),
        "threshold": threshold,
        "drifted_features": drifted,
        "alert": bool(drifted),
    }


def evidently_table(reference: pd.DataFrame, current: pd.DataFrame, columns: list[str],
                    seed: int = 42) -> tuple[pd.DataFrame, pd.DataFrame]:
    """เตรียมตารางให้ Evidently ดูค่าเดียวกับที่ใช้ตัดสิน alert

    - `<lag>_index` = ดัชนียอดขาย (ดู demand_index)
    - `article_sold` = สุ่มชื่อสินค้าถ่วงตามจำนวนชิ้นที่ขาย (qty) → distribution = product mix
      (Evidently ทดสอบทีละคอลัมน์ จึงสุ่มคอลัมน์นี้แยกได้)
    """
    rng = np.random.default_rng(seed)
    idx = {c: demand_index(reference, current, c) for c in columns}
    out = []
    for k, frame in enumerate((reference, current)):
        t = pd.DataFrame({f"{c}_index": idx[c][k].to_numpy() for c in columns})
        w = frame["qty"].clip(lower=0).to_numpy(float)
        t["article_sold"] = rng.choice(frame["article"].to_numpy(), len(t), p=w / w.sum())
        out.append(t)
    return out[0], out[1]


def evidently_report(reference: pd.DataFrame, current: pd.DataFrame, columns: list[str],
                     threshold: float, path) -> dict | None:
    """รายงาน HTML ของ Evidently (DataDriftPreset, stattest = PSI เกณฑ์เดียวกัน) บนค่าเดียวกับที่ใช้ alert"""
    try:
        from evidently import ColumnMapping
        from evidently.metric_preset import DataDriftPreset
        from evidently.report import Report
    except ImportError as exc:  # evidently อยู่ใน requirements แต่ไม่ให้ monitoring ล้มเพราะรายงานภาพ
        log.warning("ข้าม Evidently report: %s", exc)
        return None
    ref_t, cur_t = evidently_table(reference, current, columns)
    num = [c for c in ref_t.columns if c.endswith("_index")]
    mapping = ColumnMapping(numerical_features=num, categorical_features=["article_sold"])
    report = Report(metrics=[DataDriftPreset(stattest="psi", stattest_threshold=threshold)])
    report.run(reference_data=ref_t, current_data=cur_t, column_mapping=mapping)
    path.parent.mkdir(parents=True, exist_ok=True)
    report.save_html(str(path))
    result = report.as_dict()["metrics"][0]["result"]
    return {
        "html": str(path.relative_to(ROOT)),
        "share_of_drifted_columns": round(float(result["share_of_drifted_columns"]), 4),
        "dataset_drift": bool(result["dataset_drift"]),
    }


# ============================== 2) Concept drift ==============================
def wape(actual, pred) -> float:
    actual = np.asarray(actual, dtype=float)
    pred = np.asarray(pred, dtype=float)
    denom = np.abs(actual).sum()
    return float(np.abs(actual - pred).sum() / denom) if denom else 0.0


def rolling_wape(frame: pd.DataFrame, window: int = 7) -> pd.DataFrame:
    """WAPE รายวัน (รวมทุกสินค้า) และ WAPE ย้อนหลัง `window` วัน = Σ|y−ŷ| / Σy ในหน้าต่าง

    ใช้ผลรวมในหน้าต่าง (ไม่ใช่ค่าเฉลี่ยของ WAPE รายวัน) → วันที่ขายน้อยไม่ถ่วงผลเกินจริง
    """
    f = frame.assign(abs_err=(frame["actual"] - frame["pred"]).abs())
    daily = f.groupby("date").agg(abs_err=("abs_err", "sum"), actual=("actual", "sum")).sort_index()
    daily["wape_daily"] = daily["abs_err"] / daily["actual"].replace(0, np.nan)
    roll = daily[["abs_err", "actual"]].rolling(window, min_periods=window).sum()
    daily["wape_7d"] = roll["abs_err"] / roll["actual"].replace(0, np.nan)
    return daily.reset_index()


def check_concept_drift(wape_7d: float, wape_deploy: float, ratio: float) -> bool:
    """True = เกิด concept drift (ประสิทธิภาพตกเกินเกณฑ์)"""
    return wape_7d > ratio * wape_deploy


# ============================== 3) System health ==============================
P95_QUERY = ('histogram_quantile(0.95, sum by (le) '
             '(rate(request_latency_seconds_bucket{endpoint=~"/predict|/recommend"}[5m])))')
ERROR_QUERY = ('(sum(rate(requests_total{status=~"5.."}[5m])) or vector(0)) '
               '/ sum(rate(requests_total{endpoint!="/metrics"}[5m]))')


def prom_query(base_url: str, query: str, timeout: float = 3.0) -> float | None:
    """ถาม Prometheus 1 ค่า (instant query) — ต่อไม่ได้/ไม่มีข้อมูล → None"""
    url = f"{base_url.rstrip('/')}/api/v1/query?" + urllib.parse.urlencode({"query": query})
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = json.load(resp)
        value = float(data["data"]["result"][0]["value"][1])
        return None if np.isnan(value) else value
    except Exception:  # noqa: BLE001 — monitoring ต้องไม่ล้มเพราะ Prometheus ปิดอยู่
        return None


def check_system(cfg: dict, query=prom_query) -> dict:
    """p95 latency และ 5xx error rate (5 นาทีล่าสุด) เทียบ SLO

    นับเฉพาะ 5xx เป็น error ของระบบ — 422 คือ input ผิดของผู้ใช้ ระบบทำงานถูกต้องแล้ว
    """
    url = os.environ.get("PROMETHEUS_URL", cfg["monitoring"].get("prometheus_url", "http://localhost:9090"))
    p95 = query(url, P95_QUERY)
    err = query(url, ERROR_QUERY)
    slo = cfg["slo"]
    p95_ms = None if p95 is None else round(p95 * 1000, 2)
    return {
        "prometheus": url,
        "available": p95 is not None or err is not None,
        "p95_latency_ms": p95_ms,
        "error_rate": None if err is None else round(err, 5),
        "latency_alert": p95_ms is not None and p95_ms > slo["p95_latency_ms"],
        "error_alert": err is not None and err > slo["error_rate"],
    }


# ============================== Retrain policy ==============================
def should_retrain(alerts: dict[str, bool], last_trained: pd.Timestamp | None, now: pd.Timestamp,
                   every_days: int = 7) -> tuple[bool, list[str]]:
    """ตัดสินใจ retrain: ครบรอบ schedule หรือ มี alert ใดก็ได้ → คืน (ควร retrain?, เหตุผล)"""
    reasons = [f"alert:{name}" for name, on in alerts.items() if on]
    if last_trained is not None and (now - last_trained) >= pd.Timedelta(days=every_days):
        reasons.append(f"schedule:{(now - last_trained).days}d >= {every_days}d")
    return bool(reasons), reasons


def trigger_retrain(cfg: dict) -> dict:
    """เรียก pipeline เดิมของทีม (ไม่แก้โค้ดของขั้นอื่น): train (P3) → evaluate_gate (P4) → API /reload (P5)

    gate ไม่ผ่าน = ไม่ลงทะเบียน (champion ตัวเดิมให้บริการต่อ) → ปลอดภัยแม้ retrain แล้วแย่ลง
    """
    steps = {}
    before = _champion_version(cfg)
    for name, module in [("train", "src.train"), ("evaluate_gate", "src.evaluate_gate")]:
        log.info("retrain: รัน python -m %s", module)
        rc = subprocess.run([sys.executable, "-m", module], cwd=ROOT).returncode
        steps[name] = rc
        if name == "train" and rc != 0:
            return {"steps": steps, "result": "train failed"}
    api = os.environ.get("API_URL", cfg["monitoring"].get("api_url", "http://localhost:8000"))
    try:
        req = urllib.request.Request(f"{api.rstrip('/')}/reload", method="POST")
        with urllib.request.urlopen(req, timeout=120) as resp:
            steps["reload"] = json.load(resp)
    except Exception as exc:  # noqa: BLE001 — API อาจไม่ได้เปิดตอนสาธิต
        steps["reload"] = f"skip: {exc}"
    after = _champion_version(cfg)
    if steps["evaluate_gate"] != 0:
        result = f"gate ไม่ผ่าน → ไม่ลงทะเบียน, champion v{before} ให้บริการต่อ"
    elif after != before:
        result = f"promote: champion v{before} → v{after}"
    else:
        result = f"ผ่าน gate แต่ไม่ชนะ champion → ค้างเป็น challenger, champion v{before} ให้บริการต่อ"
    return {"steps": steps, "champion_before": before, "champion_after": after, "result": result}


def _champion_version(cfg: dict) -> str | None:
    try:
        from src import registry

        mv = registry.get_alias_version("champion", registry.get_client(cfg), registry.model_name(cfg))
        return None if mv is None else str(mv.version)
    except Exception:  # noqa: BLE001
        return None


# ============================== โมเดลที่ใช้วัด ==============================
def _mlflow_up(uri: str) -> bool:
    if not uri.startswith("http"):
        return True  # file store
    try:
        with urllib.request.urlopen(f"{uri.rstrip('/')}/health", timeout=3):
            return True
    except Exception:  # noqa: BLE001
        return False


def load_champion(cfg: dict):
    """โหลด champion จาก MLflow Registry → (predict_fn, feature_columns, info)"""
    import mlflow

    from src import registry

    uri = registry.tracking_uri(cfg)
    if not _mlflow_up(uri):
        raise ConnectionError(f"ต่อ MLflow ไม่ได้ที่ {uri}")
    client = registry.get_client(cfg)
    name = registry.model_name(cfg)
    mv = client.get_model_version_by_alias(name, "champion")
    model = mlflow.pyfunc.load_model(f"models:/{name}@champion")
    cols = json.loads(mlflow.artifacts.load_text(f"runs:/{mv.run_id}/feature_list.json"))
    started = client.get_run(mv.run_id).info.start_time
    info = {"source": "mlflow champion", "model_version": str(mv.version), "run_id": mv.run_id,
            "trained_at": pd.Timestamp(started, unit="ms", tz="UTC").isoformat()}
    return (lambda X: np.asarray(model.predict(X[cols]), dtype=float).ravel()), cols, info


def fit_local(train_rows: pd.DataFrame, cfg: dict):
    """สำรองเมื่อไม่มี MLflow (CI / เครื่องที่ยังไม่ได้เปิด server): LightGBM ค่า default แบบเดียวกับ
    run `lightgbm_default` ของ train.py (champion v1 ใน §5) เทรนบนช่วง train เท่านั้น"""
    from lightgbm import LGBMRegressor

    from src.train import FEATURE_COLUMNS

    model = LGBMRegressor(random_state=cfg.get("seed", 42), verbosity=-1)
    model.fit(train_rows[FEATURE_COLUMNS], train_rows["qty"])
    info = {"source": "local lightgbm_default (fallback)", "model_version": None, "trained_at": None}
    return (lambda X: model.predict(X[FEATURE_COLUMNS])), FEATURE_COLUMNS, info


# ============================== รวมทุกอย่าง ==============================
def monitor(frame: pd.DataFrame, cfg: dict, model: str = "auto", scenario: str = "custom",
            system=check_system, drift_start=None) -> tuple[dict, pd.DataFrame, tuple]:
    """frame: date, article, qty (+ actual) ทั้งประวัติ → (summary, ตาราง WAPE รายวัน, (reference, current))"""
    mon, split = cfg["monitoring"], cfg["split"]
    if "actual" not in frame.columns:
        frame = frame.assign(actual=frame["qty"])
    feats = build_features(frame[["date", "article", "qty", "actual"]],
                           lags=tuple(cfg["features"]["lags"]),
                           windows=tuple(cfg["features"]["rolling_windows"]))
    feats["date"] = pd.to_datetime(feats["date"])
    feats = feats.dropna(subset=MONITORED_FEATURES)

    reference = feats[feats["date"] <= split["train_end"]]
    deploy = feats[(feats["date"] > split["train_end"]) & (feats["date"] <= split["val_end"])]
    current = feats[feats["date"] > split["val_end"]]
    if reference.empty or deploy.empty or current.empty:
        raise ValueError("ช่วง train/validation/current ว่าง — ตรวจ split ใน config กับช่วงวันที่ของข้อมูล")

    predict = info = None
    if model in ("auto", "mlflow"):
        try:
            predict, _, info = load_champion(cfg)
        except Exception as exc:  # noqa: BLE001
            if model == "mlflow":
                raise
            log.warning("ใช้โมเดลสำรอง (โหลด champion ไม่ได้: %s)", exc)
    if predict is None:
        predict, _, info = fit_local(reference, cfg)

    # ---- data drift ----
    # data drift ดูเฉพาะ N วันล่าสุด (ไม่ใช่ทั้งช่วง current) → ไวต่อการเปลี่ยนล่าสุด
    since = current["date"].max() - pd.Timedelta(days=mon.get("drift_window_days", 14))
    recent = current[current["date"] > since]
    data = check_data_drift(reference, recent, mon["psi_threshold"])

    # ---- concept drift ----
    # baseline "WAPE ตอน deploy" (config monitoring.wape_baseline):
    #   max (ค่าเริ่มต้น) = ค่าที่สูงกว่าระหว่าง 2 แบบข้างล่าง → กันเตือนผิดทั้ง 2 สาเหตุ
    #   validation       = WAPE ช่วง validation (2 เดือน, นิ่ง) แต่ ก.ค.–ส.ค. เป็นหน้าร้อนยอดสูง error สัมพัทธ์ต่ำ
    #                      → เดือนที่ยอดลดลงเตือนผิดได้ (ทดสอบแล้วเกิดจริงบนข้อมูลสังเคราะห์)
    #   first_week       = WAPE 7 วันแรกหลัง deploy (ฤดูกาลเดียวกัน) แต่ 1 สัปดาห์มี noise สูง
    #                      → ถ้าสัปดาห์แรกบังเอิญดี จะเตือนผิด (ข้อมูลคงที่ WAPE_7d แกว่ง 0.09–0.14)
    window = mon.get("wape_window_days", 7)
    wape_val = wape(deploy["actual"], predict(deploy))
    cur = current.assign(pred=predict(current))
    daily = rolling_wape(cur, window)
    first = daily.iloc[:window]
    first_actual = first["actual"].sum()
    wape_first = float(first["abs_err"].sum() / first_actual) if first_actual else float("nan")
    mode = mon.get("wape_baseline", "max")
    has_first = len(first) == window and not np.isnan(wape_first)
    wape_deploy = {"validation": wape_val,
                   "first_week": wape_first if has_first else wape_val,
                   "max": max(wape_val, wape_first) if has_first else wape_val}[mode]
    latest = daily["wape_7d"].dropna()
    wape_7d = float(latest.iloc[-1]) if len(latest) else float("nan")
    limit = mon["wape_degradation_ratio"] * wape_deploy
    over = daily[daily["wape_7d"] > limit]
    concept = {
        "baseline": mode,
        "wape_deploy": round(wape_deploy, 4),
        "wape_validation": round(wape_val, 4),
        "wape_first_week": round(wape_first, 4),
        "wape_7d_latest": round(wape_7d, 4),
        "wape_7d_max": round(float(latest.max()), 4) if len(latest) else None,
        "ratio": mon["wape_degradation_ratio"],
        "limit": round(limit, 4),
        "first_alert_date": str(over["date"].iloc[0].date()) if len(over) else None,
        "alert": check_concept_drift(wape_7d, wape_deploy, mon["wape_degradation_ratio"]),
    }

    sysh = system(cfg)
    alerts = {"data_drift": data["alert"], "concept_drift": concept["alert"],
              "latency": sysh["latency_alert"], "error_rate": sysh["error_alert"]}
    last = pd.Timestamp(info["trained_at"]) if info.get("trained_at") else None
    retrain, reasons = should_retrain(alerts, last, pd.Timestamp.now(tz="UTC"),
                                      mon.get("retrain_every_days", 7))
    summary = {
        "scenario": scenario,
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": info,
        "windows": {
            "reference": [str(reference["date"].min().date()), str(reference["date"].max().date())],
            "deploy": [str(deploy["date"].min().date()), str(deploy["date"].max().date())],
            "current": [str(current["date"].min().date()), str(current["date"].max().date())],
            "data_drift_window": [str(recent["date"].min().date()), str(recent["date"].max().date())],
            "drift_start": None if drift_start is None else str(pd.Timestamp(drift_start).date()),
        },
        "data_drift": data,
        "concept_drift": concept,
        "system": sysh,
        "alerts": alerts,
        "retrain": {"needed": retrain, "reasons": reasons},
    }
    return summary, daily, (reference, recent)


def plot_wape(results: dict[str, pd.DataFrame], limit: float, deploy: float, drift_start, path) -> None:
    """กราฟ WAPE_7d ของแต่ละ scenario + เส้นเกณฑ์ alert"""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, 4.5))
    for name, daily in results.items():
        ax.plot(daily["date"], daily["wape_7d"], marker="o", ms=3, label=name)
    ax.axhline(deploy, color="grey", ls=":", label=f"WAPE baseline (deploy) = {deploy:.3f}")
    ax.axhline(limit, color="red", ls="--", label=f"alert = 1.2 x deploy = {limit:.3f}")
    if drift_start is not None:
        ax.axvline(pd.Timestamp(drift_start), color="black", ls="-.", lw=1, label="drift starts")
    ax.set_title("Concept drift monitor: rolling 7-day WAPE (current window)")
    ax.set_ylabel("WAPE_7d")
    ax.legend(fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130)
    plt.close(fig)


def markdown_table(summaries: list[dict]) -> str:
    """ตารางพร้อมวางใน report.md §7"""
    rows = ["| Scenario | max PSI (feature) | Data drift | WAPE deploy | WAPE_7d ล่าสุด "
            "| Concept drift | Retrain |",
            "|---|---|---|---|---|---|---|"]
    for s in summaries:
        d, c = s["data_drift"], s["concept_drift"]
        top = max(d["psi"], key=d["psi"].get)
        rows.append(
            f"| {s['scenario']} | {d['max_psi']:.3f} ({top}) | {'🔴 ALERT' if d['alert'] else '🟢 ok'} "
            f"| {c['wape_deploy']:.3f} | {c['wape_7d_latest']:.3f} (เกณฑ์ {c['limit']:.3f}) "
            f"| {'🔴 ALERT' if c['alert'] else '🟢 ok'} "
            f"| {'ใช่ (' + ', '.join(s['retrain']['reasons']) + ')' if s['retrain']['needed'] else 'ไม่'} |")
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P6 monitoring: data drift / concept drift / system")
    parser.add_argument("--scenario", choices=[*SCENARIOS, "all"], default="all",
                        help="จำลองจากข้อมูล processed (ไม่ใช้เมื่อระบุ --data)")
    parser.add_argument("--data", help="ไฟล์ parquet/csv ของยอดขายจริง (date, article, qty[, actual])")
    parser.add_argument("--model", choices=["auto", "mlflow", "local"], default="auto")
    parser.add_argument("--retrain", action="store_true", help="มีเหตุให้ retrain → รัน train → gate → reload")
    parser.add_argument("--no-evidently", action="store_true", help="ไม่สร้าง HTML ของ Evidently (เร็วขึ้น)")
    args = parser.parse_args(argv)
    cfg = load_config()

    if args.data:
        path = ROOT / args.data
        base = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
        runs = {"custom": (base, None)}
    else:
        processed = ROOT / cfg["paths"]["processed"]
        if not processed.exists():
            raise SystemExit(f"ไม่พบ {processed} — รัน python -m src.ingest ก่อน")
        base = pd.read_parquet(processed)
        start = default_start(base, cfg)
        names = SCENARIOS if args.scenario == "all" else (args.scenario,)
        runs = {sc: (simulate(base, sc, cfg, start=start), None if sc == "normal" else start) for sc in names}

    summaries, curves = [], {}
    for name, (frame, start) in runs.items():
        summary, daily, (reference, current) = monitor(frame, cfg, args.model, name, drift_start=start)
        if not args.no_evidently:
            summary["data_drift"]["evidently"] = evidently_report(
                reference, current, ALERT_FEATURES, cfg["monitoring"]["psi_threshold"],
                REPORT_DIR / f"p6_{name}_data_drift.html")
        if args.retrain and summary["retrain"]["needed"]:
            summary["retrain"]["run"] = trigger_retrain(cfg)
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        out = EVIDENCE_DIR / f"p6_{name}_summary.json"
        out.write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        summaries.append(summary)
        curves[name] = daily
        flags = [k for k, v in summary["alerts"].items() if v]
        log.info("[%s] alerts=%s retrain=%s → %s", name, flags or "none",
                 summary["retrain"]["reasons"] or "no", out.relative_to(ROOT))

    c = summaries[0]["concept_drift"]
    starts = [s for _, s in runs.values() if s is not None]
    plot_wape(curves, c["limit"], c["wape_deploy"], starts[0] if starts else None,
              EVIDENCE_DIR / "p6_wape_7d.png")
    print("\n" + markdown_table(summaries))
    sysh = summaries[0]["system"]
    print(f"\nSystem (Prometheus {sysh['prometheus']}): "
          + (f"p95 = {sysh['p95_latency_ms']} ms, 5xx rate = {sysh['error_rate']}"
             if sysh["available"] else "ต่อไม่ได้ — เปิด docker compose ก่อนถ้าต้องการตรวจ latency/error"))
    # exit 1 เฉพาะตอนเฝ้าข้อมูลจริง (--data) — โหมดจำลองตั้งใจให้มี alert อยู่แล้ว ไม่ควรทำให้ make drift ล้ม
    alerted = any(any(s["alerts"].values()) for s in summaries)
    return 1 if (args.data and alerted) else 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    raise SystemExit(main())
