"""P0 — smoke test ให้ CI เขียวตั้งแต่วันแรก; แต่ละ Phase เพิ่มไฟล์ test ของตัวเอง"""
import pandas as pd
import pytest

from src.config import load_config
from src.recommend import critical_ratio, recommended_qty
from src.split import time_split
from src.train import wape


def test_config_loads():
    cfg = load_config()
    assert cfg["seed"] == 42
    assert "gate" in cfg and "slo" in cfg


def test_wape():
    assert wape([10, 10], [10, 10]) == 0
    assert wape([10, 10], [5, 15]) == pytest.approx(0.5)


def test_newsvendor():
    assert critical_ratio(50, 20) == pytest.approx(0.6)
    assert recommended_qty(12.2, on_hand=3) == 10
    assert recommended_qty(2.0, on_hand=10) == 0
    with pytest.raises(ValueError):
        critical_ratio(10, 20)


def test_time_split_no_overlap():
    df = pd.DataFrame({"date": pd.date_range("2022-01-01", "2022-12-31")})
    tr, va, te = time_split(df, "2022-06-30", "2022-08-31")
    assert tr["date"].max() < va["date"].min() and va["date"].max() < te["date"].min()
    assert len(tr) + len(va) + len(te) == len(df)
