"""P7 — Prefect flow: validate ไม่ผ่าน → flow หยุด ไม่ train ต่อ

รัน flow จริงบน Prefect แบบชั่วคราว (prefect_test_harness) ไม่ต้องเปิด Prefect server / MLflow
"""
import json

import pandas as pd
import pandera as pa
import pytest
from prefect.testing.utilities import prefect_test_harness

from src import flow, ingest, train, validate
from src.config import ROOT, load_config


@pytest.fixture(scope="module", autouse=True)
def prefect_env():
    with prefect_test_harness():
        yield


@pytest.fixture(autouse=True)
def alert_log(tmp_path, monkeypatch):
    path = tmp_path / "validation_alerts.log"
    monkeypatch.setattr(validate, "ALERT_LOG", path)
    return path


def test_bad_sample_stops_flow(alert_log):
    cfg = load_config()
    with pytest.raises(pa.errors.SchemaErrors):
        flow.pipeline(data_path=str(ROOT / cfg["paths"]["samples_bad"]))
    assert "VALIDATION FAILED" in alert_log.read_text(encoding="utf-8")


def test_good_sample_passes_check_mode():
    cfg = load_config()
    result = flow.pipeline(data_path=str(ROOT / cfg["paths"]["samples_good"]))
    assert result["validated"] is True


def test_main_exit_code_on_bad_data():
    cfg = load_config()
    assert flow.main(["--data", str(ROOT / cfg["paths"]["samples_bad"])]) == 1


def test_full_flow_does_not_train_when_validation_fails(monkeypatch):
    """ingest ได้ข้อมูลเสีย (qty ติดลบ + สินค้าไม่รู้จัก) → train / gate ต้องไม่ถูกเรียก"""
    bad = pd.DataFrame({"date": ["2022-09-01", "2022-09-01"],
                        "article": ["CROISSANT", "PIZZA"], "qty": [-5, 10]})
    called = []
    monkeypatch.setattr(ingest, "run", lambda cfg: bad)
    monkeypatch.setattr(validate, "load_meta", lambda path=None: json.loads(
        (ROOT / load_config()["paths"]["samples_meta"]).read_text(encoding="utf-8")))
    monkeypatch.setattr(train, "main", lambda: called.append("train"))
    monkeypatch.setattr(flow.evaluate_gate, "evaluate", lambda **kw: called.append("gate"))

    with pytest.raises(pa.errors.SchemaErrors):
        flow.pipeline()
    assert called == []
