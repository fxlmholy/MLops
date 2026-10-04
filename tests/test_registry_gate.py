"""P4 — gate + registry: ผ่าน gate → challenger, ชนะ champion → promote, rollback กลับเวอร์ชันก่อน

ใช้ MLflow แบบไฟล์ (file store) ใน tmp_path จึงไม่ต้องเปิด MLflow server
"""
import mlflow
import numpy as np
import pytest
from sklearn.linear_model import LinearRegression

from src import evaluate_gate, registry
from src.config import load_config


@pytest.fixture
def mlflow_env(tmp_path, monkeypatch):
    uri = (tmp_path / "mlruns").as_uri()
    monkeypatch.setenv("MLFLOW_TRACKING_URI", uri)
    mlflow.set_tracking_uri(uri)
    cfg = load_config()
    cfg["mlflow"]["experiment"] = "test-exp"
    cfg["mlflow"]["model_name"] = "test-model"
    # artifact เก็บใน tmp_path (ไม่สร้าง mlruns/ ใน repo)
    mlflow.create_experiment("test-exp", artifact_location=(tmp_path / "artifacts").as_uri())
    mlflow.set_experiment("test-exp")
    yield cfg
    mlflow.set_tracking_uri(None)


def log_run(name: str, wape: float, with_model: bool = True) -> str:
    """จำลอง run ที่ train.py log ไว้: metric `wape` + artifact `model`"""
    with mlflow.start_run(run_name=name) as run:
        mlflow.log_metric("wape", wape)
        if with_model:
            X = np.arange(10, dtype=float).reshape(-1, 1)
            mlflow.sklearn.log_model(LinearRegression().fit(X, X.ravel()), artifact_path="model")
    return run.info.run_id


def test_passes_gate_rules():
    cfg = load_config()
    assert evaluate_gate.passes_gate({"wape": 0.27}, 0.37, cfg)[0]
    ok, reasons = evaluate_gate.passes_gate({"wape": 0.35}, 0.37, cfg)  # ดีขึ้นแค่ ~5%
    assert not ok and "WAPE" in reasons[0]
    assert not evaluate_gate.passes_gate({"wape": 0.2, "model_size_mb": 80}, 0.37, cfg)[0]
    assert not evaluate_gate.passes_gate({"wape": 0.2, "p95_latency_ms": 350}, 0.37, cfg)[0]


def test_gate_promote_reject_and_rollback(mlflow_env):
    cfg = mlflow_env
    log_run("seasonal_naive", 0.37, with_model=False)
    log_run("linear_regression", 0.32)
    log_run("lightgbm_default", 0.27)

    # รอบแรก: เลือก WAPE ต่ำสุด (lightgbm) → ผ่าน gate → champion v1
    r1 = evaluate_gate.evaluate(cfg=cfg)
    assert r1["run_name"] == "lightgbm_default" and r1["promoted"] and r1["version"] == "1"

    client = registry.get_client(cfg)
    name = cfg["mlflow"]["model_name"]
    assert str(registry.get_alias_version("champion", client, name).version) == "1"

    # v2 แย่กว่า champion (linear) → ผ่าน gate แต่ไม่ชนะ → ค้างเป็น challenger
    lin_id = evaluate_gate.latest_runs(client, "test-exp")["linear_regression"].info.run_id
    r2 = evaluate_gate.evaluate(run_id=lin_id, cfg=cfg)
    assert r2["passed_gate"] and not r2["promoted"] and r2["version"] == "2"
    assert str(registry.get_alias_version("champion", client, name).version) == "1"
    assert str(registry.get_alias_version("challenger", client, name).version) == "2"

    # gate ไม่ผ่าน → ไม่ลงทะเบียน
    bad_id = log_run("lightgbm_bad", 0.36)
    r3 = evaluate_gate.evaluate(run_id=bad_id, cfg=cfg)
    assert not r3["passed_gate"] and r3["version"] is None

    # บังคับ promote v2 แล้ว rollback กลับ v1
    registry.promote("2", client, name)
    assert str(registry.get_alias_version("champion", client, name).version) == "2"
    assert client.get_model_version(name, "1").tags["status"] == "archived"
    assert registry.rollback(client, name) == "1"
    assert str(registry.get_alias_version("champion", client, name).version) == "1"
    assert client.get_model_version(name, "2").tags["status"] == "archived"

    # ไม่มีประวัติให้ rollback ต่อแล้ว
    with pytest.raises(RuntimeError):
        registry.rollback(client, name)


def test_run_without_model_cannot_register(mlflow_env):
    naive_id = log_run("seasonal_naive", 0.37, with_model=False)
    with pytest.raises(RuntimeError):
        evaluate_gate.evaluate(run_id=naive_id, cfg=mlflow_env)
