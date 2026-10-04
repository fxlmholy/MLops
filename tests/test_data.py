"""P2 — tests ของ ingest / validate / split (ใช้ไฟล์ดิบจำลองรูปแบบเดียวกับ Kaggle)"""
import subprocess
import sys

import pandas as pd
import pandera as pa
import pytest

from src.config import ROOT
from src.ingest import cap_outliers, clean, load_raw, parse_price, to_daily
from src.split import split_from_config
from src.validate import load_meta, validate

SAMPLES = ROOT / "data" / "samples"

RAW_CSV = """,date,time,ticket_number,article,Quantity,unit_price
0,2021-01-02,08:38,150040.0,BAGUETTE,1.0,"0,90 €"
1,2021-01-02,08:38,150040.0,PAIN AU CHOCOLAT,3.0,"1,20 €"
2,2021-01-02,09:14,150041.0,BAGUETTE,2.0,"0,90 €"
3,2021-01-02,09:20,150042.0,CROISSANT,-1.0,"1,10 €"
4,2021-01-04,10:00,150050.0,BAGUETTE,4.0,"0,90 €"
5,2021-01-04,10:05,150051.0,.,1.0,"0,00 €"
6,2021-01-04,10:10,150052.0,CROISSANT,1.0,"1,10 €"
"""


@pytest.fixture
def raw_path(tmp_path):
    p = tmp_path / "raw.csv"
    p.write_text(RAW_CSV, encoding="utf-8")
    return p


def test_parse_price():
    assert parse_price("0,90 €") == pytest.approx(0.90)
    assert parse_price("12,50 €") == pytest.approx(12.5)
    assert pd.isna(parse_price("abc"))


def test_clean_drops_returns_and_dot_article(raw_path):
    df = clean(load_raw(raw_path))
    assert (df["qty"] > 0).all()
    assert "." not in set(df["article"])
    assert len(df) == 5


def test_to_daily_fills_missing_days_and_top_n(raw_path):
    daily = to_daily(clean(load_raw(raw_path)), top_n=2)
    assert set(daily["article"]) == {"BAGUETTE", "PAIN AU CHOCOLAT"}  # CROISSANT ยอดน้อยสุด ถูกตัด
    assert daily["date"].nunique() == 3  # 2, 3, 4 ม.ค. — วันที่ 3 ไม่มีขาย ต้องถูกเติม
    jan3 = daily[daily["date"] == "2021-01-03"]
    assert (jan3["qty"] == 0).all()
    baguette_jan2 = daily[(daily["date"] == "2021-01-02") & (daily["article"] == "BAGUETTE")]
    assert baguette_jan2["qty"].item() == 3


def test_cap_outliers_uses_train_period_only():
    daily = pd.DataFrame({
        "date": pd.date_range("2022-01-01", periods=6),
        "article": ["A"] * 6,
        "qty": [10, 10, 10, 10, 10, 999],
    })
    capped = cap_outliers(daily, quantile=0.999, fit_end="2022-01-05")
    assert capped["qty"].max() == pytest.approx(10)  # 999 อยู่หลัง fit_end → ถูก cap ด้วยเพดานจาก train


def test_good_sample_passes():
    df = pd.read_csv(SAMPLES / "good_sales.csv", dtype=str)
    out = validate(df, load_meta(SAMPLES / "meta.json"))
    assert len(out) == 4


def test_bad_sample_is_caught_with_all_errors():
    df = pd.read_csv(SAMPLES / "bad_sales.csv", dtype=str)
    with pytest.raises(pa.errors.SchemaErrors) as exc:
        validate(df, load_meta(SAMPLES / "meta.json"))
    checks = " ".join(exc.value.failure_cases["check"].astype(str))
    assert "greater_than_or_equal_to" in checks  # qty = -5
    assert "isin" in checks  # UNKNOWN ITEM
    assert "not_nullable" in checks  # qty ว่าง


def test_duplicate_and_missing_day_are_caught():
    meta = load_meta(SAMPLES / "meta.json")
    dup = pd.DataFrame({"date": ["2022-09-01"] * 2, "article": ["CROISSANT"] * 2, "qty": ["40", "50"]})
    with pytest.raises(pa.errors.SchemaErrors):
        validate(dup, meta)
    gap = pd.DataFrame({"date": ["2022-09-01", "2022-09-03"], "article": ["CROISSANT"] * 2,
                        "qty": ["40", "50"]})
    with pytest.raises(pa.errors.SchemaErrors):
        validate(gap, meta)


def test_stats_out_of_training_range_are_caught():
    meta = load_meta(SAMPLES / "meta.json")
    spike = pd.DataFrame({"date": ["2022-09-01"], "article": ["CROISSANT"], "qty": ["5000"]})
    with pytest.raises(pa.errors.SchemaErrors):
        validate(spike, meta)


def test_cli_exit_codes():
    def run(name):
        meta = str(SAMPLES / "meta.json")
        cmd = [sys.executable, "-m", "src.validate", str(SAMPLES / name), "--meta", meta]
        return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)

    assert run("good_sales.csv").returncode == 0
    bad = run("bad_sales.csv")
    assert bad.returncode != 0
    assert "VALIDATION FAILED" in bad.stderr


def test_split_from_config_rejects_empty_part():
    df = pd.DataFrame({"date": pd.date_range("2022-01-01", "2022-03-01")})
    cfg = {"split": {"train_end": "2022-06-30", "val_end": "2022-08-31"}}
    with pytest.raises(ValueError):
        split_from_config(df, cfg)
