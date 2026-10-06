"""P6 (M5) — test monitoring: PSI, data/concept drift, rolling WAPE, system health, retrain policy

ใช้ข้อมูลสังเคราะห์ + โมเดล local → ไม่ต้องมีข้อมูล Kaggle / MLflow / Prometheus
"""
import numpy as np
import pandas as pd
import pytest

from src import monitor
from src.config import load_config
from src.simulate_drift import drifted_articles, make_concept_drift, make_data_drift, simulate


@pytest.fixture(scope="module")
def cfg():
    c = load_config()
    c["split"] = {"train_end": "2022-03-31", "val_end": "2022-05-31"}
    return c


@pytest.fixture(scope="module")
def daily():
    """ยอดขายรายวัน 6 สินค้า (2021-10 .. 2022-06) มี pattern วันหยุดสุดสัปดาห์ + Poisson noise"""
    rng = np.random.default_rng(42)
    dates = pd.date_range("2021-10-01", "2022-06-30")
    rows = []
    for d in dates:
        for i, a in enumerate(["A", "B", "C", "D", "E", "F"]):
            lam = (120 / (i + 1)) * (1.4 if d.dayofweek >= 5 else 1.0)
            rows.append((d.strftime("%Y-%m-%d"), a, int(rng.poisson(lam))))
    return pd.DataFrame(rows, columns=["date", "article", "qty"])


def no_system(cfg):
    return {"prometheus": "-", "available": False, "p95_latency_ms": None, "error_rate": None,
            "latency_alert": False, "error_alert": False}


# ---------- PSI ----------
def test_psi_same_distribution_is_near_zero():
    rng = np.random.default_rng(0)
    assert monitor.psi(rng.normal(0, 1, 5000), rng.normal(0, 1, 5000)) < 0.02


def test_psi_shifted_distribution_exceeds_threshold():
    rng = np.random.default_rng(0)
    assert monitor.psi(rng.normal(0, 1, 5000), rng.normal(1, 1, 5000)) > 0.2


def test_psi_handles_constant_and_empty():
    assert monitor.psi([5, 5, 5], [5, 5]) == pytest.approx(0, abs=1e-6)
    assert np.isnan(monitor.psi([], [1, 2]))


def test_categorical_psi_detects_mix_change():
    ref = ["A"] * 50 + ["B"] * 50
    assert monitor.categorical_psi(ref, ["A"] * 50 + ["B"] * 50) == pytest.approx(0, abs=1e-6)
    assert monitor.categorical_psi(ref, ["A"] * 90 + ["B"] * 10) > 0.2


# ---------- simulate_drift ----------
def test_concept_drift_keeps_features_changes_actual(daily):
    out = make_concept_drift(daily, 0.6, start="2022-06-01")
    after = out["date"] >= "2022-06-01"
    assert (out["qty"] == daily["qty"].astype(float)).all()           # X เดิม
    assert np.allclose(out.loc[after, "actual"], (out.loc[after, "qty"] * 0.6).round())
    assert (out.loc[~after, "actual"] == out.loc[~after, "qty"]).all()


def test_data_drift_shifts_product_mix_only_after_start(daily):
    out = make_data_drift(daily, 2.0, start="2022-06-01")
    after = (out["date"] >= "2022-06-01").to_numpy()
    up = out["article"].isin(drifted_articles(out["article"])).to_numpy() & after
    down = after & ~up
    base = daily["qty"].astype(float).to_numpy()
    assert np.allclose(out.loc[up, "qty"], (base[up] * 2).round())
    assert np.allclose(out.loc[down, "qty"], (base[down] / 2).round())
    assert np.allclose(out.loc[~after, "qty"], base[~after])
    assert (out["actual"] == out["qty"]).all()                           # P(y|X) เดิม


def test_unknown_scenario_raises(daily, cfg):
    with pytest.raises(ValueError):
        simulate(daily, "alien", cfg)


# ---------- rolling WAPE ----------
def test_rolling_wape_uses_sums_over_window():
    frame = pd.DataFrame({"date": pd.date_range("2022-01-01", periods=7).repeat(2),
                          "actual": [10, 10] * 7, "pred": [9, 11] * 6 + [0, 0]})
    out = monitor.rolling_wape(frame, window=7)
    assert out["wape_7d"].iloc[:6].isna().all()
    assert out["wape_7d"].iloc[-1] == pytest.approx((12 * 1 + 20) / 140)


# ---------- end-to-end บนข้อมูลสังเคราะห์ ----------
@pytest.mark.parametrize("scenario,data_alert,concept_alert", [
    ("normal", False, False),
    ("concept_drift", False, True),
])
def test_monitor_separates_data_and_concept_drift(daily, cfg, scenario, data_alert, concept_alert):
    frame = simulate(daily, scenario, cfg, start="2022-06-08")
    summary, curve, _ = monitor.monitor(frame, cfg, model="local", scenario=scenario, system=no_system)
    assert summary["data_drift"]["alert"] is data_alert
    assert summary["concept_drift"]["alert"] is concept_alert
    assert summary["retrain"]["needed"] is (data_alert or concept_alert)
    assert {"wape_daily", "wape_7d"} <= set(curve.columns)


def test_monitor_detects_data_drift(daily, cfg):
    frame = make_data_drift(daily, 2.0, start="2022-06-01")
    summary, _, _ = monitor.monitor(frame, cfg, model="local", system=no_system)
    assert summary["data_drift"]["alert"]
    assert summary["data_drift"]["drifted_features"]


# ---------- system + retrain ----------
def test_check_system_flags_slo_breach(cfg):
    fake = {monitor.P95_QUERY: 0.35, monitor.ERROR_QUERY: 0.05}
    out = monitor.check_system(cfg, query=lambda url, q: fake[q])
    assert out["p95_latency_ms"] == 350 and out["latency_alert"] and out["error_alert"]


def test_check_system_when_prometheus_down(cfg):
    out = monitor.check_system(cfg, query=lambda url, q: None)
    assert not out["available"] and not out["latency_alert"] and not out["error_alert"]


def test_should_retrain_by_alert_or_schedule():
    now = pd.Timestamp("2022-09-30", tz="UTC")
    fresh, old = now - pd.Timedelta(days=2), now - pd.Timedelta(days=8)
    assert monitor.should_retrain({"data_drift": False}, fresh, now) == (False, [])
    ok, why = monitor.should_retrain({"concept_drift": True}, fresh, now)
    assert ok and why == ["alert:concept_drift"]
    ok, why = monitor.should_retrain({}, old, now)
    assert ok and why[0].startswith("schedule:")
