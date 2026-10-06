"""P2 (M2) — Pandera schema + ตรวจ anomaly → ข้อมูลเสียต้อง raise และ exit code != 0

ตรวจตาราง date × article × qty (ผลจาก ingest.py หรือไฟล์ใน data/samples/):
    1. ชนิดข้อมูล: date เป็นวันที่จริง, qty เป็นตัวเลข, ไม่มีค่าว่าง
    2. qty >= 0
    3. article อยู่ในรายชื่อสินค้าที่รู้จัก (known_items จาก meta.json)
    4. (date, article) ไม่ซ้ำ
    5. ไม่มีวันหาย — ทุกสินค้ามีครบทุกวันในช่วงของไฟล์
    6. สถิติอยู่ในช่วงของ training: mean อยู่ใน mean_train ± 3·std_train และ max <= 3 × max_train

รัน:  python -m src.validate data/samples/bad_sales.csv      (ล้ม → exit code 1)
      python -m src.validate data/samples/good_sales.csv     (ผ่าน → exit code 0)
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import pandas as pd
import pandera as pa

from src.config import ROOT, load_config

log = logging.getLogger("validate")
ALERT_LOG = ROOT / "logs" / "validation_alerts.log"


def load_meta(path: Path | None = None) -> dict:
    """อ่าน meta.json — ถ้ายังไม่เคยรัน ingest (เช่นใน CI) ใช้ meta ของไฟล์ตัวอย่างแทน"""
    cfg = load_config()
    if path is None:
        path = ROOT / cfg["paths"]["meta"]
        if not path.exists():
            path = ROOT / cfg["paths"]["samples_meta"]
    return json.loads(Path(path).read_text(encoding="utf-8"))


def no_missing_days(df: pd.DataFrame) -> bool:
    """ทุกสินค้าต้องมีแถวครบทุกวัน ตั้งแต่วันแรกถึงวันสุดท้ายของไฟล์"""
    dates = pd.to_datetime(df["date"], errors="coerce").dropna()
    if dates.empty:
        return False
    n_days = (dates.max() - dates.min()).days + 1
    per_item = dates.groupby(df["article"]).nunique()
    return bool((per_item == n_days).all())


def build_schema(meta: dict) -> pa.DataFrameSchema:
    """สร้าง Pandera schema จาก meta (รายชื่อสินค้า + สถิติของช่วง train)"""
    stats = meta["train_stats"]
    mean_low = stats["mean"] - 3 * stats["std"]
    mean_high = stats["mean"] + 3 * stats["std"]
    max_allowed = 3 * stats["max"]

    def qty(df):
        return pd.to_numeric(df["qty"], errors="coerce")

    return pa.DataFrameSchema(
        columns={
            "date": pa.Column("datetime64[ns]", nullable=False),
            "article": pa.Column(str, pa.Check.isin(meta["known_items"]), nullable=False),
            "qty": pa.Column(float, pa.Check.ge(0), nullable=False),
        },
        checks=[
            pa.Check(no_missing_days, error="มีวันหาย: บางสินค้าไม่มีข้อมูลครบทุกวัน"),
            pa.Check(lambda df: mean_low <= qty(df).mean() <= mean_high,
                     error=f"mean ของ qty อยู่นอกช่วง training [{mean_low:.1f}, {mean_high:.1f}]"),
            pa.Check(lambda df: qty(df).max() <= max_allowed,
                     error=f"qty สูงสุดเกิน 3 เท่าของค่าสูงสุดใน training ({max_allowed:.0f})"),
        ],
        unique=["date", "article"],
        coerce=True,  # แปลงชนิดก่อนตรวจ: "abc" หรือ "2022-13-45" จะถูกจับเป็น error
        strict=False,
    )


def validate(df: pd.DataFrame, meta: dict | None = None) -> pd.DataFrame:
    """ตรวจ df — ผ่านคืน df ที่แปลงชนิดแล้ว, ไม่ผ่าน raise pa.errors.SchemaErrors (รวมทุก error)"""
    meta = meta or load_meta()
    return build_schema(meta).validate(df, lazy=True)


def summarize_errors(err: pa.errors.SchemaErrors) -> str:
    """ย่อ failure cases ให้อ่านง่าย: ตรวจข้อไหนล้ม, คอลัมน์ไหน, ค่าที่ผิด"""
    fc = err.failure_cases[["column", "check", "index", "failure_case"]]
    return fc.to_string(index=False)


def alert(message: str) -> None:
    """แจ้งเตือน: log ระดับ ERROR + เขียนต่อท้าย logs/validation_alerts.log"""
    log.error(message)
    ALERT_LOG.parent.mkdir(parents=True, exist_ok=True)
    stamp = pd.Timestamp.now().isoformat(timespec="seconds")
    with open(ALERT_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{stamp}] {message}\n")


def read_any(path: str) -> pd.DataFrame:
    """อ่าน csv/parquet — csv อ่านเป็น string ทั้งหมด ให้ schema เป็นคนตัดสินว่าชนิดผิดไหม"""
    if str(path).endswith(".parquet"):
        return pd.read_parquet(path)
    return pd.read_csv(path, dtype=str, keep_default_na=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="ตรวจไฟล์ยอดขายรายวันด้วย Pandera schema")
    parser.add_argument("path", nargs="?", help="csv/parquet ที่จะตรวจ (ไม่ใส่ = data/processed)")
    parser.add_argument("--meta", help="meta.json (ไม่ใส่ = data/processed/meta.json หรือของ samples)")
    args = parser.parse_args(argv)

    path = args.path or str(ROOT / load_config()["paths"]["processed"])
    meta = load_meta(Path(args.meta) if args.meta else None)
    try:
        df = validate(read_any(path), meta)
    except pa.errors.SchemaErrors as err:
        alert(f"VALIDATION FAILED: {path} — พบ {len(err.failure_cases)} จุดผิด → หยุด pipeline")
        print(summarize_errors(err), file=sys.stderr)
        return 1
    log.info("VALIDATION PASSED: %s (%d แถว)", path, len(df))
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    sys.exit(main())
